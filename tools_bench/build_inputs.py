#!/usr/bin/env python3
"""Build inputs.json: every note every tool will see, plus the answer key.

usage: python3 build_inputs.py <pii-sanitizer repo> <ASQ-PHI synthetic_clinical_queries.txt>
"""
import json, os, re, sys

REPO, ASQ = sys.argv[1], sys.argv[2]
sys.path.insert(0, REPO)
import raw_cases, gotcha_cases, holdout_cases, stress_cases  # noqa: E402

FILL = {"PATIENT_1": "Gerald Huang", "PROVIDER_1": "Dr. Amy Feld", "PROVIDER_2": "Dr. Raj Patel",
        "RELATIVE_1": "his wife Linda Huang"}
FILL_TOKENS = sorted({w for v in FILL.values() for w in re.findall(r"\w+", v)})


def fill(t):
    return re.sub(r"\[([A-Z]+_\d)\]", lambda m: FILL[m.group(1)], t)


# Hand labels for the trap identifiers in gotcha/holdout LEAK notes (regex, case-insensitive).
# Lookaheads keep the eponym itself ("Parkinson's disease") from counting as a leak.
LEAK_RE = {
    "H01": [r"\bParkinson\b(?!'s)"], "H02": [r"\bTom\b", r"\bGraves\b(?! disease)"], "H03": [r"\bHope\b"],
    "H04": [r"\bWill\b", r"\bGrant\b"], "H05": [r"\bMay\b", r"\bBrown\b"], "H06": [r"\bLyme\b"],
    "H07": [r"\bMichael\b", r"\bFox\b"], "H08": [r"\bLinda\b", r"\bWhipple\b(?=\s+will)"],
    "H09": [r"\bJordan\b", r"\bEllis\b"], "H10": [r"\bLou\b"], "H11": [r"\bSunny\b"],
    "H12": [r"J\.K\.M\.", r"4/2/1950"],
    "J01": [r"\bCushing\b(?!'s)"], "J02": [r"\bDale\b", r"\bWilson\b(?!'s)"], "J03": [r"\bFaith\b"],
    "J04": [r"\bJoy\b", r"\bPenny\b"], "J05": [r"\bRich\b"], "J06": [r"\bNorwalk\b"],
    "J07": [r"\bSelena\b", r"\bGomez\b"], "J08": [r"\bBud\b"], "J09": [r"R\.T\.W\."], "J10": [r"\bGrace\b"],
}

out = []
for cid, kind, text, gone in raw_cases.RAW:
    out.append({"set": "raw", "id": cid, "kind": kind, "text": text, "must_go": gone})

for setname, mod in (("gotcha", gotcha_cases), ("holdout", holdout_cases)):
    for cid, trap, text in mod.CLEAN:
        out.append({"set": setname + "_clean", "id": cid, "kind": trap, "text": fill(text)})
    for cid, trap, text in mod.LEAK:
        out.append({"set": setname + "_leak", "id": cid, "kind": trap, "text": fill(text), "leak_re": LEAK_RE[cid]})

# Stress: auto labels from the templates.
for i, e in enumerate(stress_cases.EPONYMS):
    c = dict(zip(("id", "label", "kind", "text"), stress_cases.CASES[2 * i]))
    l = dict(zip(("id", "label", "kind", "text"), stress_cases.CASES[2 * i + 1]))
    s = stress_cases._surname(e)
    out.append({"set": "stress_clean", "id": c["id"], "kind": "eponym", "text": fill(c["text"]), "keep": [e]})
    pats = [r"\b%s\b" % re.escape(s)]
    m = re.search(r"Neighbor (\w+) ", l["text"])
    if m:
        pats.append(r"\b%s\b" % m.group(1))
    if "daughter Ann " in l["text"]:
        pats.append(r"\bAnn\b")
    out.append({"set": "stress_leak", "id": l["id"], "kind": l["kind"], "text": fill(l["text"]),
                "leak_re": pats, "eponym": e})
for cid, lab, kind, text in stress_cases.CASES[2 * len(stress_cases.EPONYMS):]:
    b = re.search(r"(?:on|sister) (\w+)", text.replace("[PATIENT_1]'s ", "")).group(1)
    if lab == "clean":
        out.append({"set": "stress_clean", "id": cid, "kind": kind, "text": fill(text), "keep": [b]})
    else:
        out.append({"set": "stress_leak", "id": cid, "kind": kind, "text": fill(text), "leak_re": [r"\b%s\b" % b]})

# ASQ-PHI
raw = open(ASQ, encoding="utf-8").read()
blocks = raw.split("===QUERY===")[1:]
for n, b in enumerate(blocks):
    q, tags = b.split("===PHI_TAGS===")
    gold = [json.loads(x) for x in tags.strip().splitlines() if x.strip()]
    out.append({"set": "asq", "id": f"Q{n+1:04}", "kind": "phi" if gold else "neg", "text": q.strip(), "gold": gold})

json.dump({"fill_tokens": FILL_TOKENS, "cases": out}, open(os.path.join(os.path.dirname(__file__) or ".", "inputs.json"), "w"), indent=1)
from collections import Counter
print(Counter(c["set"] for c in out))
