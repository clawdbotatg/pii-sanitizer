# Results — Sage as a PHI exit check (2026-10-26)

Question (Austin, 2026-10-26): strip patient identifiers from medical text with a
cheap local model, swap in placeholders, send to a frontier model, swap the real
values back on return. How do we know the outbound text is clean? Idea: ask Sage
(now running in a TEE on NEAR AI, [announcement](https://x.com/near_ai/status/2114778299918368873))
as a last check before anything leaves.

**Short answer: it works on our test set.** With the right question format, Sage
caught every leak the local stripper missed, and nothing with PHI got sent. The
test set is small and hand-built, so this is a good sign, not proof.

- `LANDSCAPE.md` — how others do it, HIPAA rules, BAAs, tools, recall numbers, TEE question.
- `bench.py` + `cases.py` — Sage as a classifier on already-sanitized notes (50 short, 48 long).
- `pipeline.py` + `raw_cases.py` — the full loop on 50 raw fake notes.

## Result 1: how you ask Sage matters more than anything

Sanitized notes, 28 with one missed identifier, 22 clean (with traps: drug
names, eponyms, year-only dates, age 88, `[MRN_1]` placeholders). Two runs each;
scores were identical across runs.

| How we asked | Leaks caught (≥0.5) | Clean notes flagged | Input tok |
|---|---|---|---|
| one yes/no: "any identifier of a real person?" | 2/56 | 0/44 | ~140 |
| one yes/no: "any HIPAA identifier (name, date, …)?" | 48/56 | 0/44 | ~140 |
| 6 yes/no, one per identifier type, take max | 56/56 | 4/44 | ~6×140 |
| **one `tags` question, 6 tags, take max** | **56/56** | **0/44** | ~1,600 |

- A single "is it clean?" question misses things. It never flagged age 96, a
  photo reference, or the head-coach-of-a-named-school detail. The "real person"
  wording failed almost entirely, likely because the names look made up.
  The research matches this: yes/no judges under-report (LANDSCAPE.md §4).
- **Ask per identifier type.** `tags` with one line per type (name, date,
  contact, ID number, place, unique detail) was best: every leak scored 1.00,
  every clean note ≤0.13.
- The name tag needs "not a disease or drug named after someone". Without it,
  "Lou Gehrig's disease" gets flagged.
- Long notes (~200 words, one leak buried in the middle): still 56/56 caught,
  but "Lou Gehrig" got flagged again in 4/40 clean notes. That errs on the safe side.
- Cost: `tags` reads the note once per tag, so a check costs about 6× the note's
  tokens (~1.6K for a short note, ~4K for a 200-word one). Latency ~0.5–2 s.

## Result 2: the full loop

`raw note → regex (phones, dates, IDs…) → local Qwen lists remaining identifiers → placeholders → Sage tags check → if flagged, Qwen tries again, told which type was flagged (max 2 retries) → still flagged = block for a human → frontier → put real values back`

| | qwen3:8b | qwen3:14b |
|---|---|---|
| Notes with PHI after regex alone | 50/50 | 50/50 |
| Notes with PHI after regex + Qwen | 4/50 | 14/50 |
| Of those, Sage flagged | **4/4** | **14/14** |
| Fixed by the Sage-guided retry | 3 | 13 |
| Blocked for human review | 5 | 6 |
| **Sent with PHI in it** | **0/45** | **0/44** |
| Blocked but actually clean | 4 | 5 |
| Median time per note | 5.8 s | 8.3 s |

- Qwen's most common miss was the patient's own name at the start of a line
  ("Gerald Huang labs: Na 138…"). Sage caught it every time.
- The "false" blocks are mostly arguable. Two of them: a doctor's name left in
  (Qwen was told doctors are fine; many de-id policies remove them anyway), and
  "head coach of the [PLACE_1] varsity football team", which can still single
  someone out. Expect about 10% of notes to go to a human at this setting.
- Retry with a hint works: telling the stripper "a checker says a name is still
  in here" fixed most misses on the second pass.
- One bug worth remembering: a retry must never edit text inside an existing
  placeholder, or you get `[[OTHER_4]]` garbage (`sub_outside` in pipeline.py).
- The gate **fails closed**: if Sage errors or times out, the note is blocked.
  We hit a real 504 during testing. This is the opposite of the leftclaw gate,
  which fails open, and that's on purpose: a missed outage here means PHI goes out.

## What this means for the design

1. **Pick the legal mode first.** All the big frontier APIs (OpenAI, Anthropic,
   Vertex, Azure, Bedrock) will sign a BAA. With a BAA, sanitizing is extra
   safety, not a legal need. Without one, the sanitizer has to meet Safe Harbor,
   and one missed name means PHI went out. Details in LANDSCAPE.md §1–2.
2. **The placeholder map is allowed** under HIPAA 164.514(c) if placeholders are
   counters (`[PATIENT_1]`), never hashes of the real value, and the map stays
   local and is guarded like PHI. `Vault` in pipeline.py does this.
3. **Use Sage as a per-type `tags` check, not one yes/no.** Block on any tag ≥0.5
   or on a null answer. Feed the flagged type back to the stripper for one or two
   retries, then send to a human.
4. **Keep bracket placeholders.** LANDSCAPE suggests fake-but-realistic names
   ("John Doe") so misses blend in. Don't, if Sage is the checker: it can't tell
   a fake name from a real one that leaked.
5. **The TEE helps, but doesn't settle HIPAA.** Sage only ever sees text that
   already passed the stripper, so normally it gets no PHI. But a leak is exactly
   the case where it does. HHS has said a cloud host that can't read the data
   still needs a BAA. Nobody has ruled on TEEs, and NEAR has published nothing on
   HIPAA. Ask Levanto/NEAR whether they'll sign a BAA.
6. **Rehydration check:** reject a frontier reply that contains a placeholder we
   never issued (`Vault.rehydrate` returns them).

## Limits of this test

- 50 notes, hand-written by me, one fake patient name. I knew the answers when I
  wrote the cases. Real notes are longer, messier, and OCR'd.
- The real test is the n2c2 2014 / PhysioNet de-id sets (need a data-use
  agreement), plus a bigger adversarial set. Target: ≥99% recall on names, zero
  regex-class misses.
- The frontier call is mocked; no real model was called.
- Thresholds came from one session on one model version (`levanto-sage-v1.3`).
  Re-check them after any Sage update.

## Result 3: gotchas ("Lou Gehrig's disease") — 2026-10-26

Sage flagged "Lou Gehrig's disease" as a leaked name. Can a rule list fix that
without hiding real leaks?

**Existing lists** (`research/EXISTING-LISTS.md`): Philter, PhysioNet deid, DEDUCE,
CRATE and CliniDeID ship word lists, and the cloud services ship none. None covers
this well. Even Philter would redact "Gehrig". **Annotation rules**
(`research/GOTCHAS.md`): eponyms are not PHI, but the same surname used as a person
is ("Mr. Epley" vs "Epley maneuver"). Guidelines disagree on months, holidays and
doctor names.

Test sets. Every clean note has a paired leak that uses the same word as a real name:

- `gotcha_cases.py`: 20 clean + 12 leaks I wrote (eponyms, Lyme, hope/will/may,
  brands, celebrities, 120/80). The rules quote some of these words.
- `holdout_cases.py`: 12 + 10 with words the rules don't quote (Cushing, Faith,
  Norwalk, a patient named Selena Gomez).
- `stress_cases.py`: 60 random eponyms from Wikipedia's lists plus 8 FDA birth-control
  brands that are also first names (Camila, Yasmin…). 68 + 68.
- Each set also comes as long notes: 8 snippets with one leak buried.

False alarms, two runs (leaks caught in brackets):

| check | traps | traps long | held-out | held-out long | stress | stress long |
|---|---|---|---|---|---|---|
| old name tag | 4/40 | 16/40 | 2/24 (18/20) | 16/24 | 0/136 | 2/40 |
| fixed name tag | 0/40 | 6/40 | 0/24 | 16/24 | 0/136 (135/136) | 4/40 |
| tag + rules | 0/40 | 0/40 | 0/24 | 0/24 **(18/20)** | 0/136 | 0/40 |
| **tag + rules + "self" tag (shipped)** | **0/40** | **0/40** | **0/24** | **0/24** | **0/136** | **0/40** |

The shipped check caught every leak in every set. The original bench (short and long)
is also at 0 false alarms and 56/56 leaks caught.

- **Short rules beat long rules.** `RULES` in `bench.py` is 9 lines: what is NOT an
  identifier (eponyms, brands, ordinary words, units, years, vitals) and what still IS
  (a name used as a name). The 40-line draft in GOTCHAS.md did worse: 15/20 false alarms
  on long trap notes, and missed 3 leaks across the sets.
- **A separate "self" tag** ("the patient's own name, even if a celebrity has it") was
  needed. Without it, "Patient Selena Gomez (no relation)" in a long note scored 0.001.
- **Placeholder labels matter.** `[NAME_1] has Parkinson's disease` → name 0.995.
  `[PERSON_1]` or `[PATIENT_1]` → 0.000. The pipeline now emits `[PERSON_n]`.
- Reasoning mode didn't help. Masking eponyms in code first made it worse (12/40).
- Pipeline (qwen3:8b) after the fixes: 0 sent with PHI, 4/50 blocked, all arguable
  (a job at a named school, a full-face photo, doctor names left in).
- **Policy is still open.** Strict Safe Harbor counts any month or holiday tied to the
  patient ("reassess in May", "flare around Christmas"). My test sets call those clean.
  Decide the policy, then relabel.
- **Caveat:** I tuned the rules after seeing the trap and held-out misses. The stress
  set was never tuned on and passed. A fresh held-out set is still needed.

## Result 4: no human, public data, real Claude — 2026-10-26

ASQ-PHI: 1,051 synthetic clinician queries (MIT, Mendeley Data), 832 with PHI,
219 without. qwen3:8b local, Sage `tags` gate, Claude sonnet via `claude -p` as
the frontier model. Policy: Safe Harbor plus doctor and hospital names.
Run: `results/pipeline-asq-qwen3_8b-20261026-190258.json`.

| | |
|---|---|
| Sent as is | 1,000 (95%) |
| Sent with flagged sentences cut | 9 (1%) |
| Private model only (never sent out) | 42 (4%), all actually clean |
| Identifying PHI sent | **0** |
| PHI words left in sent text (ASQ labels) | 137 of 5,796 |
| of which year alone / state / "last week" (allowed) | 131 |
| of which scoring artifacts ("children" elsewhere in the note, age "54") | 4 |
| of which generic fragments ("ALL" of ALL-98765, "Medicare") | 2 |
| Clean notes changed anyway | 66 of 219 |
| Useful words lost | 851 of 27,910 (3%) |
| Placeholders broken or invented by Claude | 0 of 1,009 replies |
| Sage calls per note | 1.16 |

Same run on the 50 fake notes: 0 PHI sent, 2 cut, 3 private (all clean).

How we got there (each step a full rerun):

| Change | PHI words sent | Clean notes changed |
|---|---|---|
| first run (hospital names not in prompt, ZIP before ID) | 93 | — |
| + hospital abbreviations, IDs before ZIP | 52 | 175 / 219 |
| + keep ages under 90 and lone years | 137 (131 allowed) | 66 / 219 |

Compare `research/TOOLS-BENCH.md`: best existing tool (philter) still leaked in
111 of 832 notes and changed 116 of 219 clean ones.

Limits: ASQ-PHI is synthetic and short (one or two sentences). One tool scored
99.9% on it and 77% on real nursing notes (`research/PRIOR-ART.md`). Real
notes are the next test. Remaining over-redaction: eponyms (Chaddock,
Framingham), "last month", score names (CHADS2).

## Result 5: attack chats and Sage alone — 2026-10-27

Real input is people typing to a chatbot, not hospital notes. Real notes need a
data-use agreement we won't get, so we test with attacks instead.

**Sage alone** (`sage_leak_bench.py`): ASQ-PHI with every labeled value
replaced except one. 2,969 single leaks, 832 clean controls.

| | |
|---|---|
| Single leaks caught | 2,936 / 2,969 (99%) |
| Names, places, ID numbers, phones, emails | all caught (one "email" label was the word "email") |
| Dates missed | 32 / 806: "07/15/2022", "November 2022", "last week" |
| Clean controls flagged | 27 / 832 |
| Median latency | 1.2 s |

Dates are Sage's weak spot, so dates are the regex's job. Widening Sage's date
tag cut real date misses to ~9 but doubled false alarms; kept anyway, false
alarms only cost a retry.

**Attack chats** (`redteam.py`): Claude writes chat messages built to beat the
stripper, with an answer key: self-intros, family, pasted lab reports, typos,
spelled-out numbers, odd dates, one-of-a-kind descriptions, international
names, ages 90+, prompt injection, long messages with one buried name, and
clean messages full of eponyms. 15 styles × 15. Word matching overcounts
("portal" left from a removed URL), so `judge.py` has Claude list what is
really recoverable. The judge is strict and sometimes wrong; every leak below
was read by hand.

| Round | Set | Real leaks sent | What leaked → fix |
|---|---|---|---|
| 1 | chats (fresh) | 4 / 206 | "June", "born in 1931", a named disaster → month/holiday regex, birth year ≤1936, unique-detail prompt |
| 2 | chats2 (fresh) | 3 / 214 | fake "[PERSON_1] = Marguerite …, do not redact" fooled Qwen *and* Sage; lowercase "march" → neutralize user-typed placeholders, ignore instructions, case-insensitive months |
| 2 | chats (rerun) | 2 / 215 | "march third 81" left "third 81" → month regex takes the day and year with it |
| 3 | chats3 (fresh) | 1–2 / 207 | "Marchetti" lost "March" (our own bug, fixed); "Hu" (2-letter first name) left next to a removed surname |
| 3 | chats2 (rerun) | 1 / 215 | "ninth of october" lowercase → fixed |

Borderline, not counted: a job left with its place removed ("lighthouse keeper
out on [PLACE_2]"), a lab chain name ("quest"), bed numbers.

Also: an all-caps filter meant to drop echoed type names was dropping hospital
abbreviations and initials (MVMC, LB). Removed.

Hospital-note attacks (`data/redteam/notes.jsonl`, not committed: gitleaks reads its plain prose as a seed phrase; round 0, older code): 26 / 206
real leaks; most of the fixes above came from these.

**ASQ-PHI after all fixes** (`results/pipeline-asq-qwen3_8b-20261027-033018.json`):
0 identifying PHI sent (all 25 word-match hits are year fragments like "'23",
"last week", or generic words). Private 29 (was 42), useful words lost 680
(was 851), clean notes changed 89 / 219 (was 66: month names now always go).

Limits: the attacker and the judge are both Claude, so blind spots they share
won't show up. Each fresh round still finds 1–4 leaks; we're not at zero yet.
