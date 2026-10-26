#!/usr/bin/env python3
"""Do gotcha rules fix Sage's false alarms without hiding real leaks?

  set -a; . ~/sage/.env; set +a
  python3 gotcha_bench.py [runs]

Variants:
  base       the tags check from bench.py, as shipped
  rules      same tags, plus a gotcha rule list in the instructions
  reason     base + reasoning:"auto"
  rules+rsn  rules + reasoning:"on"
  mask       base, but known-safe medical phrases ("X's disease", "X sign" ...) are
             swapped for [MEDICAL_TERM] in the copy Sage sees (code-side allow-list)
"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
import bench
from gotcha_cases import CASES, LONG_CASES
if os.environ.get("HOLDOUT"):
    from holdout_cases import CASES, LONG_CASES
if os.environ.get("STRESS"):
    from stress_cases import CASES, LONG_CASES
if os.environ.get("LONG"):
    CASES = LONG_CASES

RULES = bench.RULES
NAME_TAG = bench.TAGS[0]
BASE_TAGS = [{"id": "name", "name": "name: name or nickname of the patient, a relative or another "
              "private person; not a [PLACEHOLDER] and not a disease or drug named after someone"}] + \
    bench.TAGS[1:6]


EPONYM = re.compile(
    r"\b(?:[A-Z][a-zA-Z-]+(?:'s)?\s+){1,3}"
    r"(?:disease|syndrome|sign|signs|phenomenon|lymphoma|esophagus|thyroiditis|procedure|"
    r"fundoplication|catheter|line|criteria|score|point|tenderness|virus|fever|chart|plates|"
    r"features|tics)\b")


def tags_call(text, rules=False, reasoning=None, tags=None, instructions=None):
    tags = tags or BASE_TAGS
    body = {"content": bench.content(text), "question": {
        "kind": "tags", "id": "phi", "tags": tags,
        "instructions": instructions or bench.PREAMBLE + (RULES if rules else "")
                        + "Tag each kind of identifier that is still present in plain text."}}
    if reasoning:
        body["reasoning"] = reasoning
    r, ms = bench.post("/decide", body)
    per = {t["id"]: t["probability"] for t in r["result"]["tags"]}
    nulls = [t["id"] for t in r["result"]["tags"] if t.get("applies") is None]
    return max(per.values()), ms, {"per": per, "nulls": nulls, "usage": r["meta"].get("usage")}


def _agent_rules():
    """The 40-line draft from research/GOTCHAS.md, used as the instructions."""
    md = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "research", "GOTCHAS.md")).read()
    sec = md[md.index("## Draft instructions"):]
    return sec.split("```")[1].strip() + "\n"


AGENT_RULES = _agent_rules()


def masked(text):
    return EPONYM.sub("[MEDICAL_TERM]", text)


OLD_TAGS = [{"id": "name", "name": "name: a person's real name or nickname, not a [PLACEHOLDER]"}] + \
    bench.TAGS[1:6]
RULE_TAGS = bench.TAGS
VARIANTS = {
    "old": lambda t: tags_call(t, tags=OLD_TAGS),
    "base": lambda t: tags_call(t),
    "rules": lambda t: tags_call(t, rules=True, tags=RULE_TAGS),
    "reason": lambda t: tags_call(t, reasoning="auto"),
    "rules+rsn": lambda t: tags_call(t, rules=True, reasoning="on", tags=RULE_TAGS),
    "mask": lambda t: tags_call(masked(t)),
    "agent40": lambda t: tags_call(t, tags=RULE_TAGS, instructions=AGENT_RULES
                                   + "Tag each kind of identifier that is still present."),
}


def one(case, v):
    cid, label, trap, text = case
    p, ms, extra = VARIANTS[v](text)
    return {"id": cid, "label": label, "trap": trap, "variant": v, "p": p, "ms": ms, "extra": extra}


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    want = os.environ.get("VARIANTS", ",".join(VARIANTS)).split(",")
    jobs = [(c, v) for _ in range(runs) for v in want for c in CASES]
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(lambda j: one(*j), jobs))
    out = f"results/gotcha{'-holdout' if os.environ.get('HOLDOUT') else ''}{'-stress' if os.environ.get('STRESS') else ''}{'-long' if os.environ.get('LONG') else ''}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    json.dump(rows, open(out, "w"), indent=1)
    print("wrote", out)
    print(f"{'variant':10} {'false alarms':>13} {'leaks caught':>13} {'p50ms':>6}  misses / false alarms")
    for v in want:
        rs = [r for r in rows if r["variant"] == v]
        C = [r for r in rs if r["label"] == "clean"]
        L = [r for r in rs if r["label"] == "leak"]
        fa = [r["id"] for r in C if r["p"] >= .5 or r["extra"]["nulls"]]
        miss = [r["id"] for r in L if r["p"] < .5 and not r["extra"]["nulls"]]
        ms = sorted(r["ms"] for r in rs)[len(rs) // 2]
        print(f"{v:10} {len(fa):>6}/{len(C):<6} {len(L)-len(miss):>6}/{len(L):<6} {ms:6.0f}  "
              f"miss={sorted(set(miss))} fa={sorted(set(fa))}")


if __name__ == "__main__":
    main()
