# Existing tools on our test notes (2026-10-26)

Default settings, run locally (M3 Max). No Sage, no remote APIs. Scripts:
`tools_bench/`. ASQ-PHI from Mendeley Data (doi 10.17632/csz5dzp7nx.1,
sha256 `cf00e424…1fc8`), not committed.

| Tool | How it detects | RAW leaked /50 | CLEAN wrongly redacted: notes /32 (words) · stress /68 | LEAK missed: gotcha+holdout /22 · stress /68 | ASQ-PHI recall | ASQ-PHI notes leaked /832 | ASQ-PHI clean queries changed /219 | ms/note |
|---|---|---|---|---|---|---|---|---|
| Presidio 2.2.365 | spaCy lg NER + regex | 9 | 23 (59) · 42 | 6 · 2 | 0.698 | 657 | 199 | 8.6 |
| LLM Guard 0.3.16 Anonymize | DeBERTa NER + Presidio regex; no dates/places by default | 22 | 5 (7) · 17 | 8 · 5 | 0.149 | 831 | 3 | 34.7 |
| LLM Guard, dates/places/orgs on | same | 8 | 11 (28) · 21 | 6 · 5 | 0.600 | 713 | 16 | 23.7 |
| philter-lite 0.6.0 | regex + word lists + POS; redacts anything not on a safe list | **3** | 30 (92) · 59 | **2 · 2** | **0.956** | **111** | 116 | **2.7** |
| CloakLLM 0.12.7 | regex + spaCy sm NER; local-LLM pass off by default | 14 | 25 (74) · 58 | 3 · 6 | 0.604 | 797 | 147 | 3.5 |
| **Ours** (regex + qwen3:8b + Sage, LEARNINGS.md) | | 4 before Sage, **0 sent** | | | not run yet | | | ~6 s |

## Takeaways

- No tool gets 0/50. Philter leaks least but wrecks clean notes: it removed
  Lou Gehrig, Apgar, Ozempic, MICU, "joy", and 59 of 68 stress eponyms/brands.
- NER tools (Presidio, CloakLLM) both leak and over-redact. They miss
  hospitals, odd MRNs, plan IDs; CloakLLM has no dates. Presidio tags
  "55-year-old" as a date in 190 of 219 clean queries.
- LLM Guard defaults skip dates and places: 22/50 leak.
- The same traps beat all of them: common-word names (Hope, Grace, Big Mike),
  initials, small towns, "96-year-old", school names, odd ID formats.
- None checks the text before it leaves.

## Caveats

- ASQ-PHI labels give values, not positions; scored by surviving words, ±few
  points. Generic words (Dr, ID, Hospital, St) left behind not counted; counting
  them: Presidio 0.641, LLM Guard 0.124 / 0.469, philter 0.860, CloakLLM 0.541.
- ASQ-PHI counts doctor names and hospitals as PHI.
- Gotcha LEAK labels are hand-made. Only CloakLLM tried of the proxy libs.

## ASQ-PHI recall by type (Presidio / LLM Guard / wide / philter / CloakLLM)

- Location (826): 0.29 / 0.00 / 0.58 / 0.94 / 0.94
- Name (814): 0.99 / 0.38 / 0.39 / 1.00 / 1.00
- Date (806): 0.99 / 0.00 / 0.95 / 0.97 / 0.05
- MRN (305): 0.40 / 0.09 / 0.33 / 0.89 / 0.15
- Health plan number (91): 0.20 / 0.04 / 0.17 / 0.85 / 0.12
- SSN (33): 0.36 / 1.00 / 1.00 / 1.00 / 0.70
- Email (31): 0.87 / 0.48 / 0.48 / 0.90 / 0.87

## Reproduce

```bash
# W = a scratch dir; REPO = this repo; D = a fresh dir for the download
curl -sL -o $D/synthetic_clinical_queries.txt https://data.mendeley.com/public-files/datasets/csz5dzp7nx/files/96e2b100-c637-4b5d-8696-7b96bc1b6de0/file_downloaded
SM=https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
LG=https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl
uv venv -p 3.11 venv-presidio && VIRTUAL_ENV=$W/venv-presidio uv pip install presidio-analyzer presidio-anonymizer "en_core_web_lg @ $LG"
uv venv -p 3.11 venv-llmguard && VIRTUAL_ENV=$W/venv-llmguard uv pip install llm-guard "en_core_web_sm @ $SM"
uv venv -p 3.11 venv-philter && VIRTUAL_ENV=$W/venv-philter uv pip install philter-lite nltk
venv-philter/bin/python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng', download_dir='$W/venv-philter/nltk_data')"
uv venv -p 3.11 venv-cloak && VIRTUAL_ENV=$W/venv-cloak uv pip install "cloakllm[detection]" "en_core_web_sm @ $SM"
python3 -B tools_bench/build_inputs.py $REPO $D/synthetic_clinical_queries.txt
venv-presidio/bin/python tools_bench/run_tool.py presidio
VIRTUAL_ENV=$W/venv-llmguard venv-llmguard/bin/python tools_bench/run_tool.py llmguard
venv-llmguard/bin/python tools_bench/run_tool.py llmguard_wide
venv-philter/bin/python tools_bench/run_tool.py philter
venv-cloak/bin/python tools_bench/run_tool.py cloakllm
python3 tools_bench/score.py
```
