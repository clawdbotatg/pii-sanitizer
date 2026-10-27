"""ASQ-PHI (1,051 synthetic clinician queries, MIT) as pipeline cases.

Not committed. Download once:
  mkdir -p data/asq-phi && curl -sL -o data/asq-phi/synthetic_clinical_queries.txt \
    https://data.mendeley.com/public-files/datasets/csz5dzp7nx/files/96e2b100-c637-4b5d-8696-7b96bc1b6de0/file_downloaded
  # sha256 cf00e424b8d2347d019f9f34e2ad1510cb4d853605410f8314bef44df8021fc8

Labels give values, not positions. must_go = the value's words, minus generic ones
(Dr, Hospital, St ...), same rule as tools_bench/score.py, so numbers compare.
ASQ-PHI counts doctor names and hospitals as PHI; so does our policy now.
"""
import json, os, re

PATH = os.environ.get("ASQ_PHI", os.path.join(os.path.dirname(__file__), "data/asq-phi/synthetic_clinical_queries.txt"))

GENERIC = set("""dr mr mrs ms miss prof patient pt id no number num mrn ssn case site acct account
account member policy plan hospital hosp clinic medical med center centre health healthcare office
facility the of and at in st saint mt university univ email com org edu net""".split())


def gold_tokens(v):
    return [w for w in re.findall(r"\w+", v) if len(w) > 1 and w.lower() not in GENERIC]


def load():
    blocks = open(PATH, encoding="utf-8").read().split("===QUERY===")[1:]
    out = []
    for n, b in enumerate(blocks):
        q, tags = b.split("===PHI_TAGS===")
        gold = [json.loads(x) for x in tags.strip().splitlines() if x.strip()]
        toks = sorted({t for g in gold for t in gold_tokens(g["value"])})
        out.append((f"Q{n + 1:04}", "phi" if gold else "neg", q.strip(), toks))
    return out
