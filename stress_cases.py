"""Stress set built from lists I didn't pick by hand:
60 random eponyms from Wikipedia's eponym lists (data/eponym_sample.json, CC BY-SA)
and FDA drug brands that are also first names. Each clean note has a paired leak
that uses the same surname/brand as a real person's name."""
import json, os, random, re

_here = os.path.dirname(os.path.abspath(__file__))
EPONYMS = json.load(open(os.path.join(_here, "data", "eponym_sample.json")))
BRANDS = ["Camila", "Yasmin", "Errin", "Skyla", "Portia", "Ella", "Jolivette", "Lyza"]

CLEAN_T = [
    "[PATIENT_1] was evaluated for {e}; workup ongoing, follow up in clinic.",
    "Exam of [PATIENT_1] notable for {e}. Will discuss with the team.",
    "[PATIENT_1] has a history of {e}. Stable on current regimen.",
]
LEAK_T = [
    "[PATIENT_1]'s husband, Mr. {s}, asked about the plan. {e} was discussed.",
    "Neighbor {f} {s} found [PATIENT_1] on the floor. Workup for {e}.",
    "Spoke with daughter Ann {s} by phone; [PATIENT_1] stable.",
]
FIRST = ["Paul", "Rita", "Omar", "Jean", "Lena", "Hugo"]


def _surname(e):
    return re.match(r"([A-Z][a-z]+)", e).group(1)


def _build():
    rnd = random.Random(3)
    out = []
    for i, e in enumerate(EPONYMS):
        out.append((f"E{i+1:02}", "clean", "eponym", rnd.choice(CLEAN_T).format(e=e)))
        out.append((f"F{i+1:02}", "leak", "surname=eponym",
                    rnd.choice(LEAK_T).format(e=e, s=_surname(e), f=rnd.choice(FIRST))))
    for i, b in enumerate(BRANDS):
        out.append((f"B{i+1:02}", "clean", "brand=name", f"[PATIENT_1] started on {b} for contraception; counseled on missed doses."))
        out.append((f"N{i+1:02}", "leak", "name=brand", f"[PATIENT_1]'s sister {b} drove her to the visit and will help with meds."))
    return out


CASES = _build()


def _long():
    rnd = random.Random(9)
    clean = [c[3] for c in CASES if c[1] == "clean"]
    leaks = [c for c in CASES if c[1] == "leak"]
    out = [(f"EL{i+1:02}", "clean", "long", "\n\n".join(rnd.sample(clean, 8))) for i in range(20)]
    for c in rnd.sample(leaks, 20):
        s = rnd.sample(clean, 7)
        s.insert(rnd.randrange(8), c[3])
        out.append(("L" + c[0], "leak", c[2], "\n\n".join(s)))
    return out


LONG_CASES = _long()
