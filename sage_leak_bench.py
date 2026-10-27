"""Can Sage alone tell us something leaked?

Take each ASQ-PHI note with labels. Swap every labeled value for a placeholder
(the clean control), then make one copy per value where only that value is left
in. A perfect checker flags every copy and none of the controls.

  python3 sage_leak_bench.py [limit]
"""
import json, os, sys, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import asq_cases, bench
from pipeline import GATE, allowed

PH = {"NAME": "PERSON", "GEOGRAPHIC_LOCATION": "PLACE", "DATE": "DATE",
      "PHONE_NUMBER": "CONTACT", "FAX_NUMBER": "CONTACT", "EMAIL_ADDRESS": "CONTACT",
      "IP_ADDRESS": "CONTACT"}  # everything else is a number -> ID


def variants():
    blocks = open(asq_cases.PATH, encoding="utf-8").read().split("===QUERY===")[1:]
    for n, b in enumerate(blocks):
        q, tags = b.split("===PHI_TAGS===")
        q = q.strip()
        gold = [json.loads(x) for x in tags.strip().splitlines() if x.strip()]
        gold = [g for g in gold if g["value"] in q and not allowed(g["value"])]
        if not gold:
            continue
        gold.sort(key=lambda g: -len(g["value"]))  # longest first, so parts don't split wholes
        count = Counter()
        slots = []
        for g in gold:
            kind = PH.get(g["identifier_type"], "ID")
            count[kind] += 1
            slots.append((g, f"[{kind}_{count[kind]}]"))

        def build(keep=None):
            t = q
            for g, ph in slots:
                if g is not keep:
                    t = t.replace(g["value"], ph)
            return t
        cid = f"Q{n + 1:04}"
        yield cid, "control", None, build()
        for g, _ in slots:
            t = build(g)
            if g["value"] in t:  # still there after the others were swapped
                yield cid, g["identifier_type"], g["value"], t


def check(v):
    cid, kind, value, text = v
    try:
        p, ms, extra = bench.run_tags(text)
        flagged = [k for k, x in extra["per"].items() if x is None or x >= GATE]
    except Exception as e:
        flagged, ms = [f"error:{e}"], 0
    return {"id": cid, "kind": kind, "value": value, "text": text, "flagged": flagged, "ms": ms}


def main():
    vs = list(variants())
    if os.environ.get("ONLY"):  # e.g. ONLY=DATE,control
        vs = [v for v in vs if v[1] in os.environ["ONLY"].split(",")]
    if len(sys.argv) > 1:
        ids = sorted({v[0] for v in vs})[: int(sys.argv[1])]
        vs = [v for v in vs if v[0] in ids]
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(check, vs))
    os.makedirs("results", exist_ok=True)
    out = f"results/sage-leak-{time.strftime('%Y%m%d-%H%M%S')}.json"
    json.dump(rows, open(out, "w"), indent=1)

    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r["kind"]][0] += bool(r["flagged"])
        by[r["kind"]][1] += 1
    c = by.pop("control")
    print(f"clean controls flagged: {c[0]}/{c[1]}")
    tot = [sum(x[0] for x in by.values()), sum(x[1] for x in by.values())]
    print(f"single leaks caught:    {tot[0]}/{tot[1]}")
    for k, (a, n) in sorted(by.items(), key=lambda x: -x[1][1]):
        print(f"  {k:32} {a}/{n}")
    ms = sorted(r["ms"] for r in rows if r["ms"])
    print(f"median {ms[len(ms) // 2]:.0f} ms   saved {out}")


if __name__ == "__main__":
    main()
