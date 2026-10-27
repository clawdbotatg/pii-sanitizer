"""Gretel PII masking v1 (Apache 2.0), health documents only, as pipeline cases.

Not committed. Build once (needs duckdb):
  mkdir -p data/gretel && for s in test validation; do curl -sL -o data/gretel/$s.parquet \
    https://huggingface.co/datasets/gretelai/gretel-pii-masking-en-v1/resolve/main/data/$s-00000-of-00001.parquet; done
  duckdb -c "copy (select uid, domain, document_type, entities, text from read_parquet('data/gretel/*.parquet')
    where domain in ('healthcare','healthcare-administration','pharmaceuticals-biotechnology'))
    to 'data/gretel/health.jsonl' (format json)"

Short synthetic documents, heavy on ID numbers and birth dates. Labels we don't
count as patient data under our policy are dropped (company, state, country, time).
"""
import ast, json, os

from asq_cases import gold_tokens

PATH = os.path.join(os.path.dirname(__file__), "data/gretel/health.jsonl")
SKIP = {"company_name", "state", "country", "time"}


def load():
    out = []
    for line in open(PATH, encoding="utf-8"):
        r = json.loads(line)
        vals = [e["entity"] for e in ast.literal_eval(r["entities"]) if not set(e["types"]) <= SKIP]
        toks = sorted({t for v in vals for t in gold_tokens(v)})
        out.append((f"G-{r['uid'][:8]}", "phi" if toks else "neg", r["text"], toks))
    return out
