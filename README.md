# pii-sanitizer

Use frontier AI models on medical data without sending them patient identity.

## The idea

1. A cheap local model removes names, dates, phone numbers, IDs, addresses and
   so on from the text, and swaps in placeholders like `[NAME_1]`.
2. **Before anything leaves, Sage checks it.** Sage is Levanto's fast yes/no
   model, now running inside a TEE on NEAR AI.
3. If Sage finds something, the local model tries again, told what Sage found.
   If it still fails, a person reviews it.
4. Clean text goes to the frontier model (Claude, GPT, etc.).
5. The answer comes back, and the placeholders get swapped back to the real
   values locally. The real values never leave the machine.

The hard part has always been step 2: how do you know the text is clean?
That's what this repo is about.

## Goal

A drop-in proxy: send it medical text, get back the frontier model's answer
with real names restored, and an exit check you can trust. "Trust" means
measured recall on standard medical de-identification datasets, not just our
own test notes.

## Where it stands (2026-10-26)

Working prototype, tested on 50 fake notes:

- Sage caught every note the local model missed. Nothing with patient data
  went out.
- It only works if you ask Sage about each type of identifier separately.
  A single "is this clean?" missed 1 in 7 leaks.
- About 10% of notes get blocked for a person to review.
- A short gotcha rule list stops false alarms on things like "Lou Gehrig's
  disease" without hiding real names. Checked on 60 random eponyms. Details in
  `RESULTS.md` Result 3.

Everything learned, short: `LEARNINGS.md`. Full numbers: `RESULTS.md`. How others do this, and the HIPAA rules:
`LANDSCAPE.md`. Gotcha research: `research/GOTCHAS.md` (what is and isn't PHI)
and `research/EXISTING-LISTS.md` (open-source word lists).

## Next

1. Pick the date policy (strict Safe Harbor flags "in May" and "Christmas").
2. Test on real de-identification datasets (n2c2 2014, PhysioNet). Needs a
   data-use agreement.
3. Hook up a real frontier model in place of the mock.
4. Ask Levanto/NEAR whether they will sign a HIPAA agreement (a BAA). The TEE
   alone doesn't cover it.
5. Wrap it as a proxy with an OpenAI/Anthropic-compatible API.

## Files

- `pipeline.py` — the full loop: regex → local model → Sage check → retry → send → restore.
- `bench.py`, `cases.py` — different ways of asking Sage, compared on sanitized notes.
- `raw_cases.py` — raw fake notes with the answers, for `pipeline.py`.
- `gotcha_bench.py` + `gotcha_cases.py`, `holdout_cases.py`, `stress_cases.py` —
  false-alarm traps ("Lou Gehrig's disease" vs "Mr. Gehrig").
- `data/eponym_sample.json` — 60 eponyms from Wikipedia's eponym lists (CC BY-SA).
- `results/` — raw output of every run.

All patient data here is made up.

## Run it

```
export SAGE_API_KEY=lv_live_...          # Austin's is in ~/sage/.env
python3 pipeline.py qwen3:8b             # needs ollama running with that model
python3 bench.py 2                       # compare question styles, 2 runs
LONG=1 STRATS=tags python3 bench.py 2    # same, on long notes
```
