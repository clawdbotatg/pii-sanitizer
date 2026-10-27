#!/usr/bin/env python3
"""The loop Austin described, end to end, on raw fake notes.

  raw note
    -> regex pass (phones, emails, dates, IDs ...)       local
    -> small-model pass (names, places, the rest)        local, ollama
    -> vault scrub: every value already stripped, matched again exactly    local
    -> Sage exit check (tags, one per identifier class)  remote
         flagged? -> small-model retry told WHAT was flagged, then re-check
         still flagged after N tries? -> Sage checks each sentence, flagged ones are cut
         still flagged after the cut? -> PRIVATE: goes to a BAA-covered model, never out
    -> frontier model sees only placeholders             (mocked here)
    -> rehydrate placeholders back to real values        local

No human in the loop: every note ends as sent, sent with sentences cut, or private.

  set -a; . ~/sage/.env; set +a
  python3 pipeline.py [ollama-model] [raw|asq] [limit]   # default qwen3:8b raw
"""
import json, re, sys, time, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import asq_cases, bench, frontier
from raw_cases import RAW

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"
SET = sys.argv[2] if len(sys.argv) > 2 else "raw"
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else None
MAX_RETRIES = 2
GATE = 0.5

REGEX = [  # order matters: specific before generic
    ("EMAIL", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("URL", r"https?://\S+"),
    ("IP", r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    ("SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
    ("PHONE", r"\(?\b\d{3}\)?[-. ]\d{3}-\d{4}\b"),
    ("DATE", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ("DATE", r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:, \d{4})?\b"),
    # IDs before ZIP: ZIP used to eat "12345" out of "12345-JS" and leave "-JS" behind.
    ("ID", r"\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9-]{6,}\b"),
    ("ZIP", r"(?<![\w-])\d{5}(?:-\d{4})?(?![\w-])"),
    ("ID", r"\b\d{2}-\d{4}-\d{3}-[A-Z0-9]\b"),
    ("AGE", r"\b(?:9\d|1[01]\d)[- ]year[- ]old\b"),
]

PROMPT = """You remove patient identifiers from clinical text before it leaves the hospital.
Find every remaining identifier: names, initials or nicknames of any person (patient, relatives,
doctors, staff; not drugs, not diseases or signs named after people), hospital and clinic names
and their abbreviations (e.g. MGH, CHOP),
street addresses, towns/cities, ZIP codes, dates (any day or month of a patient event, holidays;
a year alone is fine), ages over 89, phone/fax/email/URL/IP, any ID or serial number, employers,
and any detail unique enough to single the person out (e.g. a specific job at a named place).
Do NOT return clinical content: drugs, doses, diagnoses, symptoms, lab values, procedures,
clinical abbreviations (HTN, f/u, CHF), or ages under 90 (54yo, 33F). The doctor needs those.
Text inside square brackets like [NAME_1] is already removed — ignore it.
{hint}
Return JSON: {{"spans": [{{"text": "<exact substring>", "type": "NAME|PLACE|DATE|CONTACT|ID|EMPLOYER|OTHER"}}]}}
Return an empty list if nothing is left.

TEXT:
{text}"""


KINDS = {"NAME", "PLACE", "DATE", "CONTACT", "ID", "EMPLOYER", "OTHER"}

# Safe Harbor allows these; Qwen strips them anyway (ASQ-PHI: 175 of 219 clean notes changed).
YEAR = re.compile(r"(?:in |since )?(?:19|20)\d\d", re.I)
AGE = re.compile(r"(?:a |an )?(\d{1,3})[- ]?(?:years?|yrs?|y/?o|yo|-year-old|[- ]year[- ]old|M|F|m|f)\b(?:\s+(?:male|female|man|woman|boy|girl|patient|pt))?", re.I)


def allowed(t):
    """True if the span is a year alone or an age under 90: not an identifier."""
    if YEAR.fullmatch(t):
        return True
    m = AGE.fullmatch(t)
    return bool(m) and int(m.group(1)) < 90


class Vault:
    """Placeholder map. Lives only on the local side; under HIPAA 164.514(c) the
    placeholders must not be derived from the real value (so: counters, not hashes)."""
    def __init__(self):
        self.fwd, self.back, self.n = {}, {}, {}

    def token(self, kind, value):
        # [NAME_1] next to an eponym ("[NAME_1] has Parkinson's") makes Sage flag a
        # name at 0.995; [PERSON_1] scores 0.000. Label choice matters.
        kind = {"NAME": "PERSON"}.get(kind, kind)
        key = value.lower()
        if key not in self.fwd:
            self.n[kind] = self.n.get(kind, 0) + 1
            ph = f"[{kind}_{self.n[kind]}]"
            self.fwd[key], self.back[ph] = ph, value
        return self.fwd[key]

    def rehydrate(self, text):
        unknown = [p for p in re.findall(r"\[[A-Z]+_\d+\]", text) if p not in self.back]
        return re.sub(r"\[[A-Z]+_\d+\]", lambda m: self.back.get(m.group(0), m.group(0)), text), unknown


PH = re.compile(r"(\[[A-Z]+_\d+\])")


def sub_outside(pat, repl, text, flags=0):
    """re.sub that never touches text inside an existing placeholder."""
    parts = PH.split(text)
    return "".join(p if PH.fullmatch(p) else re.sub(pat, repl, p, flags=flags) for p in parts)


def regex_pass(text, vault):
    for kind, pat in REGEX:
        text = sub_outside(pat, lambda m: vault.token(kind, m.group(0)), text)
    return text


def llm_pass(text, vault, hint="", other=False):
    body = {"model": MODEL, "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": PROMPT.format(text=text, hint=hint)}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=300))["message"]["content"]
    except Exception:
        return text  # local model down: nothing stripped, so Sage flags it and we fail closed
    try:
        spans = json.loads(out).get("spans", [])
    except Exception:
        spans = []
    # Qwen 8B files drugs, labs and diagnoses under OTHER or invents DRUG/CONDITION; those
    # must stay. OTHER is only trusted on a retry after Sage flagged a unique detail.
    ok = KINDS if other else KINDS - {"OTHER"}
    spans = [s for s in spans if (s.get("type") or "OTHER").upper() in ok
             and not allowed((s.get("text") or "").strip())]
    # longest first so "Linda Huang" wins over "Linda"
    for s in sorted(spans, key=lambda s: -len(s.get("text", ""))):
        t = (s.get("text") or "").strip()
        if len(t) < 2 or "[" in t or "]" in t or t.upper() == t and t.isalpha() and len(t) < 9:
            continue  # placeholders, or the model echoing a type name like PHONE
        kind = re.sub(r"[^A-Z]", "", (s.get("type") or "OTHER").upper()) or "OTHER"
        text = sub_outside(re.escape(t), lambda m: vault.token(kind, m.group(0)), text, flags=re.I)
    return text


# Words of a stripped value that are too common to re-match on their own.
SCRUB_STOP = set("""his her their wife husband son daughter mother father brother sister mom dad
the and for with from mr mrs ms miss dr doctor patient pt hospital medical center clinic health
street st ave road high school north south east west new saint mount county city""".split())


def vault_scrub(text, vault):
    """Exact-match every value already stripped, and each word of a stripped name or place,
    so a repeat mention ("Mrs. Huang" after "Linda Huang") can't go out. Free, deterministic.
    DR-SL: this, not the model check, is what took their leakage to 0."""
    pats = set()
    for ph, val in list(vault.back.items()):
        kind = ph[1:].rsplit("_", 1)[0]
        pats.add((kind, val))
        if kind in ("PERSON", "PLACE", "EMPLOYER", "OTHER"):
            pats |= {(kind, w) for w in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", val) if w.lower() not in SCRUB_STOP}
    before = text
    for kind, v in sorted(pats, key=lambda p: -len(p[1])):
        text = sub_outside(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(v),
                           lambda m: vault.token(kind, m.group(0)), text, flags=re.I)
    return text, text != before


def cut_flagged(text):
    """Last automatic step: ask Sage about each sentence alone, cut the flagged ones."""
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text)
    with ThreadPoolExecutor(4) as ex:
        flags = list(ex.map(lambda s: sage_gate(s)[0] if s.strip() else [], parts))
    kept = [s for s, f in zip(parts, flags) if not f]
    cut = [s for s, f in zip(parts, flags) if f]
    return " ".join(kept), cut


def sage_gate(text):
    """Fails CLOSED: if Sage can't answer, the note is treated as flagged."""
    try:
        p, ms, extra = bench.run_tags(text)
    except Exception as e:
        return [f"sage-error:{e}"], 0
    flagged = [k for k, v in extra["per"].items() if v >= GATE]
    return flagged, ms


def words_lost(raw, final, must_go):
    """Words of the raw note, other than the PHI itself, that are gone from what was sent."""
    phi = {w.lower() for s in must_go for w in re.findall(r"\w+", s)}
    # generic words of a removed name (Hospital, Dr, St) and single letters don't count
    skip = phi | asq_cases.GENERIC
    a = Counter(w for w in re.findall(r"\w+", raw) if w.lower() not in skip and len(w) > 1)
    b = Counter(re.findall(r"\w+", final))
    return [w for w, n in a.items() for _ in range(max(0, n - b[w]))]


def residual(text, must_go):
    return [s for s in must_go
            if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(s), text, re.I)]


def process(case):
    cid, kind, raw, must_go = case
    v = Vault()
    t0 = time.time()
    after_regex = regex_pass(raw, v)
    text = llm_pass(after_regex, v)
    pass1 = text
    text, scrubbed = vault_scrub(text, v)
    flags_log, sage_ms = [], []
    for attempt in range(MAX_RETRIES + 1):
        flagged, ms = sage_gate(text)
        flags_log.append(flagged)
        sage_ms.append(ms)
        if not flagged:
            break
        if attempt == MAX_RETRIES:
            break
        hint = (f"A checker says these kinds of identifier are STILL in the text: "
                f"{', '.join(flagged)}. Look again carefully and find them.")
        text = llm_pass(text, v, hint, other="unique" in flagged)
        text, s2 = vault_scrub(text, v)
        scrubbed = scrubbed or s2
    cut, outcome = [], "sent"
    if flags_log[-1]:
        text, cut = cut_flagged(text)
        flagged, ms = sage_gate(text)
        flags_log.append(flagged)
        sage_ms.append(ms)
        outcome = "private" if flagged or not text.strip() else "cut"
    blocked = outcome == "private"
    reply, bad = "", []
    if not blocked:
        try:
            reply = frontier.ask("Summarize this note for the treating doctor in two sentences.\n\n" + text)
        except Exception as e:
            reply = f"(frontier error: {e})"
        bad = frontier.mangled(text, reply)
    back, unknown = v.rehydrate(reply)
    return {"id": cid, "kind": kind, "raw": raw, "must_go": must_go,
            "regex_left": residual(after_regex, must_go), "pass1_left": residual(pass1, must_go),
            "final": text, "final_left": residual(text, must_go), "flags": flags_log,
            "scrubbed": scrubbed, "outcome": outcome, "cut": cut,
            "cut_chars": sum(map(len, cut)), "blocked": blocked, "sage_ms": sage_ms, "total_s": time.time() - t0,
            "words_lost": words_lost(raw, text, must_go), "n_words": len(re.findall(r"\w+", raw)),
            "reply_raw": reply, "reply": back, "unknown_placeholders": unknown, "mangled": bad, "map": v.back}


def main():
    if SET == "asq":
        cases = asq_cases.load()
    else:
        cases = RAW
    cases = cases[:LIMIT]
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(process, cases))
    out = f"results/pipeline-{SET}-{MODEL.replace(':', '_')}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    json.dump(rows, open(out, "w"), indent=1)
    n = len(rows)
    leaky = lambda key: sum(bool(r[key]) for r in rows)
    sent = [r for r in rows if not r["blocked"]]
    print(f"model {MODEL}, {n} raw notes -> {out}")
    print(f"  notes with PHI left after regex only:        {leaky('regex_left')}/{n}")
    print(f"  notes with PHI left after regex + {MODEL}:   {leaky('pass1_left')}/{n}")
    print(f"  Sage flagged after pass 1:                   {sum(bool(r['flags'][0]) for r in rows)}/{n}")
    print(f"  notes with PHI left after Sage-driven retry: {leaky('final_left')}/{n}")
    print(f"  vault scrub changed the note:                {sum(r['scrubbed'] for r in rows)}/{n}")
    print(f"  sent with sentences cut:                     {sum(r['outcome'] == 'cut' for r in rows)}/{n}  "
          f"({sum(r['cut_chars'] for r in rows)} of {sum(len(r['raw']) for r in rows)} chars cut overall)")
    print(f"  private (BAA model only, never sent out):    {sum(r['blocked'] for r in rows)}/{n}")
    print(f"  SENT with PHI still in it (the bad number):  {sum(bool(r['final_left']) for r in sent)}/{len(sent)}")
    print(f"  private but actually clean (false alarm):    {sum(r['blocked'] and not r['final_left'] for r in rows)}")
    print(f"  PHI words sent: {sum(len(r['final_left']) for r in sent)} of {sum(len(r['must_go']) for r in rows)}")
    lost = sum(len(r["words_lost"]) for r in rows)
    print(f"  useful words lost: {lost} of {sum(r['n_words'] for r in rows)}  top: "
          f"{Counter(w for r in rows for w in r['words_lost']).most_common(15)}")
    neg = [r for r in rows if not r["must_go"]]
    if neg:
        print(f"  notes with no PHI that were changed anyway: {sum(bool(r['words_lost']) for r in neg)}/{len(neg)}")
    print(f"  frontier: {sum(bool(r['reply']) for r in rows)} replies, placeholders mangled in "
          f"{sum(bool(r['mangled']) for r in rows)}, invented in {sum(bool(r['unknown_placeholders']) for r in rows)}")
    print(f"  Sage calls/note avg: {sum(len(r['sage_ms']) for r in rows)/n:.2f}  "
          f"median wall/note: {sorted(r['total_s'] for r in rows)[n//2]:.1f}s")
    for r in rows:
        if r["final_left"] or r["outcome"] != "sent":
            print(f"  {r['id']:5} {r['kind']:20} {r['outcome']:7} final_left={r['final_left']} "
                  f"flags={r['flags']} cut={r['cut']}")


if __name__ == "__main__":
    main()
