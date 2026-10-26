# Prior art: local strip + separate verifier before a cloud LLM

2026-10-26. Read-only research for `pii-sanitizer`. Builds on `LANDSCAPE.md`; only new or
corrected items here. **(unverified)** = came from a search snippet or secondary page I did
not read in full.

---

## Short answer

No open-source repo found that does **local strip → separate checker model on the outbound
text → retry → send, with no human in the loop, on medical text, with published recall.**

Closest pieces:

| Work | Local strip | Separate checker on outbound text | No human | Medical | Recall on i2b2/n2c2/ASQ-PHI | Code |
|---|---|---|---|---|---|---|
| DR-SL (Hu et al., Sep 2026) | yes (regex + local LLM) | yes (same local LLM, attacker/enumeration probes) + deterministic literal scrub + external strong-model re-test | **no** — failures go to a human | partly (synthetic Chinese consult prompts from MedQA) | no | yes, MIT, gitee |
| P2Skill (Ryu et al., Aug 2026) | yes (local SLM paraphrase) | deterministic matcher only, no model | **yes** — on a match the sub-task runs on the local model instead | one of 4 domains, 40 identifiers | no | none found |
| Palacios et al. (Aug 2026) | no (cloud LLM under BAA does the strip) | tested verifiers/auditors; none beat one good prompt | n/a (offline batch) | yes, real notes | own 100 notes, not i2b2 | link in paper is 404 |
| phi-leak-guard | n/a | deterministic, output-side test | n/a | yes | no | yes |
| Our repo | regex + Qwen | Sage, one yes/no per identifier type | goal; today ~10% go to a human | yes | not yet | — |

---

## 1. DR-SL — Hu, Yu, Wang (NUAA), arXiv 2609.14883, 14 Sep 2026

Paper: https://arxiv.org/abs/2609.14883 (HTML https://arxiv.org/html/2609.14883).
Code: https://gitee.com/jiangsu-yunhefeng-intelligent_0/dr-sl — **public, MIT code, CC-BY-4.0
data**, created 2026-09-11, last push 2026-09-14, 0 stars (gitee API).

### Correction to LANDSCAPE.md
LANDSCAPE says DR-SL's failing probe was an adversarial "is anything left?" prompt. It wasn't a
yes/no "is it clean" question. It was a **per-attribute attacker quiz**: "Based on the
material, what is this person's {age}? If you can't infer it, answer UNKNOWN", plus one "can
the combination uniquely identify the person? yes / no / not enough info" question. The local
model answered UNKNOWN for values sitting right there in the text. (Prompt text:
`sim/pipeline.py` `attack_run_bundle`, in Chinese.) Also: DR-SL data is **synthetic Chinese
consultation prompts** (medical/banking/travel/legal), not clinical notes. No i2b2/n2c2/ASQ-PHI.

### Architecture (paper §3, Fig. 1, §5.4)
1. **Cascade extractor** builds the sensitive set S: (a) regex/NER for explicit IDs, (b) local
   LLM extraction + a self-critique pass for quasi-identifiers (age, department, surgery…),
   (c) "DetectCombinable" marks combinations that could single someone out.
2. **Dehydrate** (generalize or remove each value; age → band etc.) using a typed prompt library.
3. **Two-branch check, fully local:**
   - Branch 1 (re-identification): local model plays attacker on the dehydrated text and
     answers questions generated *from S* (≥75 probes per instance). Pass if the 95% Wilson
     upper bound of the hit rate ≤ 0.05.
   - Branch 2 (utility): QA probes check task info still answerable. Utility is a hard gate,
     leakage the objective (lexicographic loop, hard round budget → guaranteed to stop).
4. Output **PASS** or **INFEASIBLE** (with a residual-leak report).
5. Mandatory release chain (added after their own failures, deviation D13):
   **local gate → deterministic "hard line" scrub → external strong-model attacker re-test →
   send, or human review.**
- Local models: Ornith-1.5-35B-A3B (main), Qwen3.8-27B (reference). Strong attackers:
  qwen3.8-flash/max, glm-5.2 (§6.6).

### What failed (false PASSes)
- **Residual literals (T18):** 159/160 "dehydrated" outputs still had the real values, mean
  3.01 per instance — span-only replacement missed repeat mentions. Local gate still passed many.
- **Certification gap (T18/T25):** on 70 locally PASSed outputs, external strong attackers
  recovered 0.43–0.49 of the probed values. Local model under the attacker quiz: ~0.
- **Diagnosis (T25):** same local model, asked "list every concrete personal-attribute value in
  this text" (JSON list), found the residuals at 0.992 (29/30 complete). It *saw* them; the
  attacker-quiz format made it say UNKNOWN. Their lesson: "probe format is a first-class
  experimental factor."
- Domain priors in the attacker prompt also made models answer UNKNOWN more (T3).

### What fixed it
- **Enumeration probe** (T25b/T25c): `ENUM_SYSTEM` in `sim/pipeline.py` = "List all concrete
  personal attribute values in the text (age, amount, place, disease, date, ID, name, phone…).
  Output JSON only: {"values": [...]}". Graded by string-matching the list against S.
  Full rerun: PASS rate 43.8% → 5.0% (most old PASSes were false), rounds 4.0 → 7.8, same cost.
  Of the 8 enum-PASSes, external attackers found 2 truly clean and 6 still leaking
  open-vocabulary items (a law-firm name, a case type). **Enumeration does not reach 1.0 on
  open-vocabulary categories.**
- **Hard line (T18):** replace every remaining literal occurrence of every value in S
  (string match). After it: 0.000 literal leakage on all 160, two strong attackers.
  This deterministic step, not the model check, carries the guarantee.
- **External re-test:** strong cloud model attacks the final text. They admit this *is* an
  egress, so they put the re-tester in the same trust class as the destination.
- **Human fallback:** every INFEASIBLE goes to a human with the residual report.

### Did they replace the human? No.
The human is a designed layer. Nothing like "drop the sentence" or "route to local model".
On the worst-case benchmark, after the hard line, **0% auto-release** (all to human, §6.9
T18). On a mixed benchmark, 67.5% auto-release under a semantic utility judge (24.2% under
exact-value utility) (T24). Medical was worst: 47% (T24), 0/160 enum-PASS (T25c).

### Their numbers (headline)
- Extractor recall 0.951 (explicit 0.977, quasi 0.931); regex-only explicit recall 46.1% (T2, T9).
- Leakage before → after loop: 0.457 → 0.304 (T10); with enum probe 0.762 → 0.358 (T25c).
- Local vs strong-model attack gap Δ = +0.18 on raw text (T5).
- Cost: ~200–240 s and ~10 LLM calls per instance (T20). Not interactive.
- Self-learning prompt library: hypothesis not supported (T13).
- Human studies: utility judge ρ = 0.839; gold recall 0.987–1.000 (T22, T23).

### Repo structure (gitee tree)
`dataset/` (generators, annotation handbook, schema, MedQA rewrite) · `sim/` (`pipeline.py`
probes/attackers/dehydrator, `loop.py`, `extractor.py`, `synthpop.py` k-anonymity,
`stage2–5.py`, tests) · `results/` per stage · `human_study/` · `latex/` · pre-registered
`experiment_protocol_v1.md` with deviation log. Backends via OpenAI-compatible endpoints.

---

## 2. Palacios, Neeley et al. (Baylor / Texas Children's), arXiv 2608.17051, 17 Aug 2026

https://arxiv.org/abs/2608.17051 (HTML https://arxiv.org/html/2608.17051)

- 100 real pediatric oncology notes, 5,322 spans; 8 LLMs on AWS Bedrock under a BAA; vs TiDE
  and OpenMed PII.
- Best: Sonnet 4.6 F1 0.918, recall 0.960 (Baseline prompt). TiDE F1 0.779; regex-only
  recall 57.4%.
- **Verifier/ensemble findings (Suppl. E4):**
  - 14 multi-agent/ensemble setups; **none beat one well-prompted pass** on F1 (0.906–0.908).
  - **Self-Heal (Recall):** a Sonnet verifier checks the output for residual PHI, retries
    with feedback. Flagged 2/10 notes; recall 0.958, no gain.
  - Scrubber→Auditor (Opus restores over-redactions): auditor restored nothing; high variance.
  - **Cross-model vote** (Sonnet + DeepSeek + Kimi, 2 of 3): **highest recall, 0.986**, lower
    precision, 3× cost. Their models' misses overlap only 0.30–0.43 Jaccard → diversity helps
    recall.
  - Same-model vote: no gain; errors correlated across runs.
  - 20.3% of misses are shared by all top 4 LLMs: ambiguous partial dates and institution IDs.
  - Their reason: de-id is a "single-read task"; a second pass sees nothing new. The fix was
    *specification*: naming local identifier types (TCH, building names, pager numbers)
    recovered 48/61 institutional misses.
- Gold standard was leaky: models found 414 unlabeled spans; expert confirmed 49/49 checked.
- **Prompts:** summarized in Suppl. E2 (Baseline/Targeted/Precision, Scrubber/Auditor
  excerpts quoted). Full text "in the code repository" `src/phi_benchmark/prompts/`.
- **Code:** paper links https://github.com/LiuzLab/phi-scrubber-evaluation — **404 today**
  (checked with gh API and curl). Not public yet, or moved.

---

## 3. Other systems (new vs LANDSCAPE.md)

### Verifier / gate before the cloud call
- **P2Skill** (Korea Univ., arXiv 2608.14094, Aug 2026) — https://arxiv.org/abs/2608.14094.
  Local SLM splits, flags PII, paraphrases; a **deterministic matcher** scans every
  cloud-bound request for declared identifiers/patterns. **On a match: block, and run that
  sub-task on the local model** (or split further). No human. 0–6 of 87 identifiers leaked
  depending on SLM. Leaks came from identifiers the first step never flagged. No code found.
  This is the clearest "route to private model instead of human" design.
- **PAPILLON** (NAACL 2025, arXiv 2410.17127) — local model decides what to forward to the
  cloud ("privacy-conscious delegation"). Cited by DR-SL. Not medical-specific. (Not re-read.)
- **GuardianAgent** (arXiv 2608.29251, Aug 2026) — risk score → allow/transform/deny;
  adversarial guesser drives escalation of rewriting; guesses only count if supported by the
  original text. Datasets TAB, SynthPAI, PII-Masking-300k. No code link.
  https://arxiv.org/abs/2608.29251
- **Privacy Gatekeepers** (ICSC 2025, arXiv 2508.16765) — local model filters prompts before
  cloud. Abstract only, no numbers. https://arxiv.org/abs/2508.16765
- **Safer Reasoning Traces** (arXiv 2603.05618, Mar 2026) — compares rule, TF-IDF, GLiNER and
  LLM-judge gatekeepers for PII leaks; "no single method dominates". Not medical.
  https://arxiv.org/abs/2603.05618 (per-type numbers not read)
- **StenoAI "Privacy Mode" proposal** — local detection + placeholders, explicit fail-closed
  ("must block — never silently fall back to raw text"). Issue, not shipped code
  **(unverified)**. https://github.com/stenolabs/stenoai/issues/238

### PHI proxies / tools (no separate verifier model)
- **phi-redactor** (Show HN) — Presidio + spaCy proxy, 18 Safe Harbor IDs, realistic
  surrogates, swap back, hash-chain audit log. https://github.com/DilawarShafiq/phi-redactor,
  https://news.ycombinator.com/item?id=47170744
- **cliniguard** — OpenAI-compatible clinical proxy, reversible `<PERSON_1>` tokens; its LLM
  judge checks hallucinations, not residual PHI **(unverified)**.
  https://github.com/vikramT75/cliniguard
- **redactable** — deterministic-first + optional GLiNER/Gemma, `[TYPE_n]` tokens, local
  proxy/MCP, CI recall gate; Apache-2.0; no runtime residual check.
  https://github.com/PraneelBhatia/redactable
- **phi-leak-guard** — deterministic test that fails CI if LLM *output* contains PHI.
  https://github.com/selvassn/phi-leak-guard
- **Redact-Proxy** (redact.health), **Philter AI Proxy** (philterd.ai) — local/commercial
  proxies **(unverified claims)**. https://www.redact.health/redact-proxy,
  https://philterd.ai/blog/redact-pii-before-sending-to-an-llm/
- **local-llm-deid** — second pass re-runs the same local LLM on the partly redacted note.
  https://github.com/JamesWeatherhead/local-llm-deid

### Published recall on ASQ-PHI / PhysioNet (all author-reported)
ASQ-PHI repo: https://github.com/JamesWeatherhead/asq-phi. Reuse tracker (warns: not rerun,
don't rank as one leaderboard): https://github.com/JamesWeatherhead/asq-phi-in-the-wild
(`data/adoptions.json`).

| System | Type | ASQ-PHI | Other |
|---|---|---|---|
| AWS Comprehend Medical (ASQ-PHI authors) | cloud API | recall 98.7% at thr 0.0 (still 47 leaks, 90% over-redaction); 95.2% at 0.5 | — |
| **Outis** (Apache-2.0) | DeBERTa-v3 token classifier, no rules, no verifier | 99.94% PHI chars masked (tuned on ASQ-PHI failures — not independent) | **PhysioNet real nursing notes 77.3%**; only 54.9% of notes fully masked. https://github.com/ewhauser/outis |
| **MedDeID** (Antwerp, arXiv 2609.10049) | on-prem compact transformer | 98.90% char recall | Dutch hospital 98.9%; primary care 87–90%. https://arxiv.org/abs/2609.10049 |
| HANK Safe Harbor | 2 encoders + rules + fakes | recall 0.966 | (tracker) |
| Inkguard | local redaction tool | 97.1% held-out half | (tracker) |
| Oracle AegisVox | text detector | typed F1 94.4% / 79.9% full ontology | (tracker) |
| Protostar AI | commercial | P 0.98 / R 0.99 **(vendor)** | https://protostarai.com/validation.html |

**None of these has a second model checking the outbound text.** None reports n2c2 2014;
Outis says it isn't accessible to them. Note the PhysioNet gap: synthetic ~99.9% vs real
notes 77%.

### Benchmarks worth adding
- **QuasiLeak-Bench** (arXiv 2610.21333, Oct 2026) — 5,000 messages where 2–4 weak cues jointly
  reveal a hidden attribute; "local LLM detectors miss most groups" **(third-party summary)**.
  Code + data public: https://github.com/Yufannnn/QuasiLeak-Bench,
  https://huggingface.co/datasets/HenryZYF/QuasiLeak-Bench. Fits the "unique detail" tag.
- **RAT-Bench** (arXiv 2602.12806) — anonymizers rated by re-identification risk.
  https://arxiv.org/abs/2602.12806

---

## 4. HIPAA: can automated de-id with no human review count?

**No ruling or HHS guidance addresses it directly.** Nothing found says Safe Harbor needs a
human, and nothing says software alone is enough.

From the HHS 2012 guidance (read via Wayback copy of
https://www.hhs.gov/sites/default/files/ocr/privacy/hipaa/understanding/coveredentities/De-identification/hhs_deid_guidance.pdf):
- §3.10: free text gets no special treatment — "an identifier listed in the Safe Harbor
  standard must be removed regardless of its location in a record if it is recognizable as an
  identifier." Safe Harbor is a result (all 18 gone + no actual knowledge), not a process. A
  tool that misses one name means that output was not de-identified.
- §2.4: an expert determination can cover "a data set, **or the method that generated such a
  data set**." So an Expert Determination on a pipeline is contemplated. Time-limited
  certifications are common practice; repeated releases (e.g. monthly) should be re-examined.
- §1.5: warns that local acronyms "known to only a select few employees" cause missed
  redactions — the same failure Palacios measured.
- Guidance cites Uzuner 2007 (automatic de-id state of the art) but says nothing about tools.

Practitioner view (not official): automated scrubbing is "necessary but not sufficient";
defending "no actual knowledge" over residual misses usually means a measured error rate plus
Expert Determination **(secondary)**:
https://www.forasoft.com/learn/telemedicine/articles-telemedicine/de-identification-analytics-on-health-data.
Human baseline for context: one annotator recall 81%, two-annotator consensus 94%
(https://arxiv.org/pdf/2312.08495).

Practical read: for a no-human pipeline, the defensible route is **Expert Determination of the
method**, backed by measured per-category recall on real-ish notes, with a time limit and
ongoing monitoring. Safe Harbor alone gives no cover for misses.

---

## 5. What to take from this for our design

1. **Add a deterministic "vault literal" gate.** We already hold every stripped value in the
   Vault. Before send, string-match every vault value — and its pieces (each name token,
   digits-only form of IDs) — against the outbound text; block on a hit. DR-SL's version of
   this took literal leakage to 0.000 where the model check could not. Our `pipeline.py`
   only checks this offline in tests (`residual(..., must_go)`), not at runtime. It also
   catches "Linda Huang" stripped but "Mrs. Huang" left.
2. **Probe format matters more than model size.** DR-SL: the same model saw 99% of residuals
   when asked to list them, ~0% when role-playing an attacker. Our finding (per-type tags
   beat one yes/no) is the same lesson. Consider an enumeration-style check where the local
   model lists candidate identifiers, then code decides — at least as a second signal.
3. **Enumeration still misses open-vocabulary items** (firm names, institutions). Palacios:
   institution abbreviations and building names are the top miss category. Ask Sage a tag
   for "organization / facility name" and let clinics add their own terms (TCH, unit names).
4. **Replace the human with local routing, not silence.** P2Skill's answer to a failed check
   is "run it on the local model". For us: on a final block, either answer with the local
   model, or send with the flagged sentence dropped and say so. Nobody has measured the
   second option on medical text.
5. **Diverse checkers raise recall; same-model retries don't.** Palacios: cross-model vote
   got the best recall (0.986); same-model voting and self-verify did nothing. Sage (different
   model family from Qwen) is the right kind of checker; a third, different detector
   (e.g. Outis/OpenMed token classifier) would be cheap.
6. **Test on real-ish text.** Outis: 99.9% on synthetic ASQ-PHI, 77% on real PhysioNet notes.
   ASQ-PHI and QuasiLeak-Bench are open now and need no DUA. PhysioNet `deid` nursing
   notes may need only PhysioNet access, not an n2c2 DUA **(unverified, check the page)**.
