#!/usr/bin/env python3
"""Score out/<tool>.json against inputs.json. usage: python3 score.py [tools...]"""
import json, os, re, statistics, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = sys.argv[1:] or ["presidio", "llmguard", "llmguard_wide", "philter", "cloakllm"]
inp = json.load(open(os.path.join(HERE, "inputs.json")))
FILL = set(inp["fill_tokens"])
CASES = inp["cases"]


def words(t):
    return re.findall(r"[A-Za-z0-9]+", t)


# Words inside a gold span that identify nobody on their own: titles, field labels,
# generic facility words. Leaving "Dr." or "Hospital" behind is not a leak.
GENERIC = set("""dr mr mrs ms miss prof patient pt id no number num mrn ssn case site acct account
account member policy plan hospital hosp clinic medical med center centre health healthcare office
facility the of and at in st saint mt university univ email com org edu net""".split())


def gold_tokens(v):
    t = [w for w in words(v) if len(w) > 1 and w.lower() not in GENERIC]
    return t


def survives(tok, out):
    return re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(tok), out, re.I) is not None


def lost_words(src, out):
    """Words of src (minus the filled-in fake PHI) that are missing from out."""
    a = Counter(w for w in re.findall(r"\w+", src) if w not in FILL)
    b = Counter(re.findall(r"\w+", out))
    return [w for w, n in a.items() for _ in range(max(0, n - b[w]))]


report = {}
for tool in TOOLS:
    R = json.load(open(os.path.join(HERE, "out", tool + ".json")))
    r = {"examples": defaultdict(list)}
    get = lambda c: R[c["set"] + "/" + c["id"]]["out"]
    # RAW
    leaked, miss_kinds, miss_str = [], Counter(), Counter()
    for c in (c for c in CASES if c["set"] == "raw"):
        o = get(c)
        left = [s for s in c["must_go"] if s.lower() in o.lower()]
        if left:
            leaked.append((c["id"], left))
            miss_kinds[c["kind"]] += 1
            miss_str.update(left)
    r["raw_leaked"] = len(leaked)
    r["raw_detail"] = leaked
    r["raw_miss_strings"] = miss_str.most_common()
    # CLEAN (gotcha + holdout): token diff
    for s in ("gotcha", "holdout"):
        notes, lost = 0, []
        for c in (c for c in CASES if c["set"] == s + "_clean"):
            lw = lost_words(c["text"], get(c))
            if lw:
                notes += 1
                lost.append((c["id"], lw))
        r[s + "_clean_notes"] = notes
        r[s + "_clean_words"] = sum(len(x) for _, x in lost)
        r[s + "_clean_detail"] = lost
        # LEAK
        miss = []
        for c in (c for c in CASES if c["set"] == s + "_leak"):
            o = get(c)
            hit = [p for p in c["leak_re"] if re.search(p, o, re.I)]
            if hit:
                miss.append((c["id"], hit))
        r[s + "_leak_missed"] = len(miss)
        r[s + "_leak_detail"] = miss
    # stress
    over = [c["id"] for c in CASES if c["set"] == "stress_clean" and not all(k in get(c) for k in c["keep"])]
    r["stress_clean_over"] = len(over)
    r["stress_clean_detail"] = over
    smiss = []
    for c in (c for c in CASES if c["set"] == "stress_leak"):
        o = get(c)
        if c.get("eponym"):
            o = o.replace(c["eponym"], " ")  # an intact eponym is not a leak
        hit = [p for p in c["leak_re"] if re.search(p, o)]
        if hit:
            smiss.append((c["id"], hit))
    r["stress_leak_missed"] = len(smiss)
    r["stress_leak_detail"] = smiss
    # ASQ-PHI
    spans = caught = soft = lit = 0
    by_type = defaultdict(lambda: [0, 0])
    notes_leak, missed_vals = 0, defaultdict(list)
    neg_changed, neg_lost = 0, Counter()
    for c in (c for c in CASES if c["set"] == "asq"):
        o = get(c)
        if not c["gold"]:
            lw = [w for w in words(c["text"]) if w not in words(o)]
            lw = lost_words(c["text"], o)
            if lw:
                neg_changed += 1
                neg_lost.update(lw)
            continue
        any_leak = False
        for g in c["gold"]:
            toks = gold_tokens(g["value"])
            spans += 1
            lit += not any(survives(t, o) for t in words(g["value"]))
            if not toks:  # e.g. "J.K." or "email": fall back to the literal value
                toks = [g["value"]] if g["value"].lower() != "email" else []
            by_type[g["identifier_type"]][0] += 1
            left = [t for t in toks if (survives(t, o) if t.isalnum() else t.lower() in o.lower())]
            if not left:
                caught += 1
                by_type[g["identifier_type"]][1] += 1
            else:
                any_leak = True
                missed_vals[g["identifier_type"]].append(g["value"])
            if len(left) < len(toks):
                soft += 1
        notes_leak += any_leak
    r["asq_literal_recall"] = lit / spans
    r["asq_spans"], r["asq_recall"], r["asq_soft_recall"] = spans, caught / spans, soft / spans
    r["asq_notes_leaked"] = notes_leak
    r["asq_pos_notes"] = sum(1 for c in CASES if c["set"] == "asq" and c["gold"])
    r["asq_neg_changed"] = neg_changed
    r["asq_neg_total"] = sum(1 for c in CASES if c["set"] == "asq" and not c["gold"])
    r["asq_neg_top_lost"] = neg_lost.most_common(12)
    r["asq_by_type"] = {k: {"n": v[0], "recall": round(v[1] / v[0], 3)} for k, v in sorted(by_type.items(), key=lambda kv: -kv[1][0])}
    r["asq_missed_examples"] = {k: v[:8] for k, v in missed_vals.items()}
    ms = [x["ms"] for x in R.values()]
    rawms = [R["raw/" + c["id"]]["ms"] for c in CASES if c["set"] == "raw"]
    asqms = [R["asq/" + c["id"]]["ms"] for c in CASES if c["set"] == "asq"]
    r["ms_median_all"], r["ms_mean_raw"], r["ms_mean_asq"] = statistics.median(ms), statistics.mean(rawms), statistics.mean(asqms)
    r["errors"] = sum(1 for x in R.values() if x["err"])
    del r["examples"]
    report[tool] = r

json.dump(report, open(os.path.join(HERE, "results.json"), "w"), indent=1)
hdr = ["tool", "RAW leaked/50", "gotcha CLEAN notes over / words", "holdout CLEAN notes over / words", "stress CLEAN over /68",
       "LEAK missed (gotcha /12, holdout /10)", "stress LEAK missed /68", "ASQ recall (literal)", "ASQ recall", "ASQ recall soft",
       "ASQ notes leaked", "ASQ negatives changed", "ms raw", "ms asq"]
print(" | ".join(hdr))
for t, r in report.items():
    print(" | ".join(map(str, [t, r["raw_leaked"], f'{r["gotcha_clean_notes"]}/20 · {r["gotcha_clean_words"]}',
        f'{r["holdout_clean_notes"]}/12 · {r["holdout_clean_words"]}', r["stress_clean_over"],
        f'{r["gotcha_leak_missed"]} , {r["holdout_leak_missed"]}', r["stress_leak_missed"],
        f'{r["asq_literal_recall"]:.3f}', f'{r["asq_recall"]:.3f}', f'{r["asq_soft_recall"]:.3f}', f'{r["asq_notes_leaked"]}/{r["asq_pos_notes"]}',
        f'{r["asq_neg_changed"]}/{r["asq_neg_total"]}', f'{r["ms_mean_raw"]:.1f}', f'{r["ms_mean_asq"]:.1f}'])))
