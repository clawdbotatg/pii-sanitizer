"""Held-out traps: none of these words appear in the RULES text in bench.py.
Checks that the gotcha rules generalize instead of matching their own examples."""

CLEAN = [
    ("K01", "eponym-disease", "[PATIENT_1] worried about Alzheimer's after her mother's diagnosis. MoCA 28/30. Reassured."),
    ("K02", "eponym-disease", "[PATIENT_1] with Cushing's syndrome workup: late-night salivary cortisol elevated x2. Addison's ruled out."),
    ("K03", "eponym-disease", "[PATIENT_1] has Huntington's in the family; genetic counseling offered. Also Wilson's disease excluded."),
    ("K04", "eponym-disease", "[PATIENT_1], 6yo, with Kawasaki disease; IVIG given. Echo: no coronary aneurysm."),
    ("K05", "eponym-syndrome", "[PATIENT_1] with Marfan habitus, Ehlers-Danlos ruled out. Guillain-Barré history in 2015."),
    ("K06", "eponym-virus", "[PATIENT_1] Epstein-Barr IgM positive. Also Norwalk virus outbreak in her dorm. Supportive care."),
    ("K07", "eponym-sign", "[PATIENT_1]: Trousseau sign positive, Chvostek negative, Homans negative. Calcium 7.1."),
    ("K08", "eponym-procedure", "[PATIENT_1] s/p Roux-en-Y bypass and Billroth II. Now with dumping syndrome."),
    ("K09", "common-word", "[PATIENT_1] has faith the treatment will work; joy returned to her days. Rose 2 lbs. Grace period on bills ended."),
    ("K10", "common-word", "[PATIENT_1] got a penny-sized lesion on the shin, rich in vessels; sandy texture on dermoscopy."),
    ("K11", "famous-person", "[PATIENT_1] asked if her symptoms are like what Selena Gomez described with lupus. Explained."),
    ("K12", "brand", "[PATIENT_1] switched from Trulicity to Mounjaro; uses a FreeStyle Libre 3. Wegovy denied by insurance."),
]

LEAK = [
    ("J01", "surname=eponym", "Mrs. Cushing, 52F, referred for Cushing's syndrome evaluation."),
    ("J02", "surname=eponym", "[PATIENT_1]'s brother Dale Wilson was also tested for Wilson's disease."),
    ("J03", "name=common-word", "Her daughter Faith brought [PATIENT_1] in after a fall at home."),
    ("J04", "name=common-word", "[PATIENT_1]'s caregiver Joy Penny reports poor oral intake."),
    ("J05", "name=common-word", "Husband Rich called; [PATIENT_1] refused her evening meds again."),
    ("J06", "town=virus", "[PATIENT_1] works at a daycare in Norwalk and three kids there are sick."),
    ("J07", "famous-name-as-patient", "Patient Selena Gomez (no relation), 29F, here for lupus follow-up."),
    ("J08", "nickname", "Pt goes by 'Bud' around the ward. [PATIENT_1] has Addison's, on hydrocortisone."),
    ("J09", "initials", "Pt R.T.W. presents with Kawasaki-like rash; 4yo; mother at bedside."),
    ("J10", "first-name-only", "Grace says the dizziness started Monday. [PATIENT_1] is 70 and on lisinopril."),
]

CASES = [(i, "clean", t, x) for i, t, x in CLEAN] + [(i, "leak", t, x) for i, t, x in LEAK]


def _long():
    import random
    rnd = random.Random(23)
    body = [t for _, _, t in CLEAN]
    out = [(f"KL{i+1:02}", "clean", "long-traps", "\n\n".join(rnd.sample(body, 8))) for i in range(12)]
    for lid, trap, leak in LEAK:
        snips = rnd.sample(body, 7)
        snips.insert(rnd.randrange(8), leak)
        out.append((f"JL{lid[1:]}", "leak", trap, "\n\n".join(snips)))
    return out


LONG_CASES = _long()
