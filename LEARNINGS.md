# What we learned (2026-10-26)

Everything learned so far, in one place. The numbers behind each point are in
`RESULTS.md`.

## The check that works

Ask Sage one `tags` question with one tag per identifier type: name, date,
contact, ID number, place, unique detail, and "self". Block if any tag scores
0.5 or higher, or comes back null. The exact wording is `TAGS` and `RULES` in
`bench.py`.

- **One yes/no "is this clean?" misses leaks.** It missed 8 of 56, including
  age 96 and a photo reference. Asking "any identifier of a real person?"
  missed 54 of 56, probably because the names look made up.
- **Short rules beat long rules.** A 9-line list of what is and isn't an
  identifier fixed the false alarms. A 40-line version did worse: more false
  alarms and 3 missed leaks.
- **The "self" tag** ("the patient's own name, even if a celebrity has it") is
  needed. Without it, "Patient Selena Gomez (no relation)" in a long note
  scored 0.001.
- **Placeholder labels change the answer.** `[NAME_1] has Parkinson's disease`
  scores 0.995 for "name". `[PERSON_1]` or `[PATIENT_1]` scores 0.000. Use
  `[PERSON_n]`.
- **Long notes are harder.** Every false alarm we saw got worse when one leak
  was buried in about 200 words. Always test long notes, not only short ones.
- Reasoning mode didn't help. Masking known disease names in code before Sage
  sees the text made things worse.
- Scores were nearly identical across runs. Still run everything twice.
- Cost: `tags` reads the note once per tag, so a check is about 7× the note's
  tokens. Latency is about 0.5 to 1 s.

## Gotchas: what is and isn't patient data

Not identifiers:
- Diseases, signs, scores, procedures and tools named after people or places:
  Lou Gehrig's disease, Parkinson's, Lyme disease, Whipple, Apgar, Babinski.
- Drug and device brands, ordinary words (hope, will, may), hospital units
  (MICU, 4 West), a year alone, vitals like 120/80.
- A famous person the patient only talks about.

Still identifiers, even when the word is also a disease or an ordinary word:
- A name used as a name: "Mr. Parkinson", "daughter Hope", "sister Camila"
  (Camila is also a birth-control brand).
- The patient's own name, even if a celebrity shares it.
- A town the patient lives in (Old Lyme, Norwalk), initials, nicknames.

Still undecided:
- Strict HIPAA counts any month or holiday tied to the patient ("reassess in
  May", "flare around Christmas"). Our tests treat these as fine. Pick a
  policy.
- Doctor names. HIPAA doesn't require removing them, but many teams do.

## Existing lists (research/EXISTING-LISTS.md)

- Philter (BSD-3) has 195k safe words and big name lists. "Gehrig" is on its
  last-name list, so it would redact "Lou Gehrig's disease" too.
- PhysioNet deid has 7,298 "ambiguous" names, like Hope, May and Parkinson,
  that only count as names when context says so. It's the closest fit to our
  problem.
- CRATE, DEDUCE and CliniDeID have real eponym lists, but they're GPL-3.
- Cloud services (AWS, Google, Azure) and LLM guardrail tools ship no list,
  only an empty allow-list option.
- Nobody covers clinical scores, named devices, drug brands that are also
  names, or diseases named after patients ("Lou Gehrig").
- Best use of the lists: generating test cases. Our stress set came from them:
  60 random Wikipedia eponyms plus FDA brand names.

## Guidelines (research/GOTCHAS.md)

- German and Dutch guidelines say eponyms are not patient data. The US i2b2
  guidelines don't mention eponyms. The Spanish one tags "Down syndrome".
- HHS says: initials and the last 4 digits of an SSN count. A year alone
  doesn't. Doctor names don't have to go.
- Old tools only treat a dictionary word as a name when there's a cue: Mr./Dr.,
  first + last name, son/wife, "reports". That's the same idea as our rules.

## The pipeline

- Regex alone left PHI in all 50 notes. Adding a local Qwen model left it in 4
  (8B) or 14 (14B). The bigger model did worse.
- Qwen's most common miss was the patient's name at the start of a line
  ("Gerald Huang labs: …").
- Sage flagged every one of those misses. Telling Qwen which type Sage flagged
  fixed most of them on the retry.
- Result: 0 notes sent with PHI. About 8 to 10% of notes are blocked for a
  person to review, and every block was arguable (a job at a named school, a
  full-face photo, doctor names).
- A retry must never edit text inside an existing placeholder, or you get
  `[[OTHER_4]]` garbage. That's `sub_outside` in `pipeline.py`.
- The check fails closed: if Sage errors, the note is blocked. We hit a real
  504 during testing.

## HIPAA and the TEE (LANDSCAPE.md)

- All the big frontier APIs sign a BAA (OpenAI, Anthropic, Google, Azure,
  Bedrock). With one, sanitizing is extra safety, not a legal must.
- A placeholder map is allowed if placeholders are counters, never hashes of
  the real value, and the map stays local.
- A TEE doesn't remove the need for a BAA. Sage only sees text that already
  passed the stripper, but when the stripper misses something, Sage sees the
  leak. NEAR has said nothing about HIPAA.
- Published research agrees that a single yes/no checker under-reports leaks.

## Testing mistakes to avoid

- Don't write rules that quote your test cases. Some of our rules did, so we
  added a held-out set and a stress set built from lists we didn't hand-pick.
- The held-out set is no longer fully clean, because one rule was fixed after
  seeing its miss. The stress set was never tuned on, and it passed.
- In this machine's zsh, `env $X` where X is "A=1 B=1" does not split into
  two variables. Two "long" test runs silently ran on short notes because of
  this. Set variables explicitly and check the case IDs in the output.

## Next

1. Pick the date and doctor-name policy, then relabel the tests.
2. Build a fresh held-out set that nobody has tuned on.
3. Run on n2c2 2014 and PhysioNet (needs a data-use agreement).
4. Call a real frontier model instead of the mock.
5. Ask Levanto/NEAR whether they'll sign a BAA.
