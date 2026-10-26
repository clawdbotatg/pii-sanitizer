#!/usr/bin/env python3
"""Run one redaction tool over inputs.json, default settings, write out/<tool>.json.

usage: <tool venv>/bin/python run_tool.py {presidio|llmguard|philter|cloakllm}
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
tool = sys.argv[1]


def make_presidio():
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    an, anon = AnalyzerEngine(), AnonymizerEngine()  # default: spaCy en_core_web_lg + built-in regex recognizers

    def f(t):
        return anon.anonymize(text=t, analyzer_results=an.analyze(text=t, language="en")).text
    return f


def make_llmguard():
    from llm_guard.vault import Vault
    from llm_guard.input_scanners import Anonymize

    sc = Anonymize(Vault())  # defaults: DeBERTa-v3 AI4Privacy NER + Presidio regex, threshold 0.5

    def f(t):
        s, _ok, _score = sc.scan(t)
        return s
    return f


def make_llmguard_wide():
    """Not default: LLM Guard with its NER's other labels + dates switched on."""
    from llm_guard.vault import Vault
    from llm_guard.input_scanners import Anonymize
    from llm_guard.input_scanners.anonymize import DEFAULT_ENTITY_TYPES
    sc = Anonymize(Vault(), entity_types=DEFAULT_ENTITY_TYPES + ["LOCATION", "ORGANIZATION", "DATE_TIME"])

    def f(t):
        s, _ok, _score = sc.scan(t)
        return s
    return f


def make_philter():
    import philter_lite
    cfg = os.path.join(os.path.dirname(philter_lite.__file__), "configs", "philter_delta.toml")
    filters = philter_lite.load_filters(cfg)

    def f(t):
        inc, _exc, _dt = philter_lite.detect_phi(t, patterns=filters)
        return philter_lite.transform_text_asterisk(t, inc)
    return f


def make_cloakllm():
    from cloakllm import Shield, ShieldConfig
    sh = Shield(ShieldConfig(log_dir=os.path.join(HERE, "cloak-audit")))  # defaults: regex + spaCy en_core_web_sm NER; LLM pass off

    def f(t):
        s, _map = sh.sanitize(t)
        return s
    return f


fn = {"presidio": make_presidio, "llmguard": make_llmguard, "llmguard_wide": make_llmguard_wide, "philter": make_philter, "cloakllm": make_cloakllm}[tool]()
cases = json.load(open(os.path.join(HERE, "inputs.json")))["cases"]
fn("Warm up: John Smith called 555-123-4567 on 01/02/2020.")
res = {}
for c in cases:
    t0 = time.perf_counter()
    try:
        o = fn(c["text"])
        err = None
    except Exception as e:  # record, keep going
        o, err = c["text"], repr(e)
    res[c["set"] + "/" + c["id"]] = {"out": o, "ms": (time.perf_counter() - t0) * 1000, "err": err}
os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
json.dump(res, open(os.path.join(HERE, "out", tool + ".json"), "w"), indent=1)
print(tool, "done", len(res), "errors:", sum(1 for r in res.values() if r["err"]))
