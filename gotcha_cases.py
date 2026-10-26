"""Hard cases: things that look like identifiers but aren't, and the same words
used as real identifiers. Paired where possible, so a checker can't pass by
ignoring a word everywhere. All made up.
"""

CLEAN = [  # (id, trap, text) — nothing here identifies the patient
    ("G01", "eponym-disease", "[PATIENT_1] read about Lou Gehrig's disease online and is worried about her muscle twitching. EMG normal. Reassured."),
    ("G02", "eponym-disease", "[PATIENT_1] has Parkinson's disease with resting tremor, on carbidopa-levodopa. Also Hashimoto's thyroiditis."),
    ("G03", "eponym-disease", "[PATIENT_1] with Crohn's disease, prior ileocecal resection. Now on Humira. No flare."),
    ("G04", "eponym-many", "[PATIENT_1]: Hodgkin lymphoma in remission, Raynaud phenomenon, Barrett esophagus on surveillance, Graves disease s/p RAI."),
    ("G05", "eponym-signs", "Exam of [PATIENT_1]: positive Murphy sign, negative McBurney point tenderness, Kernig and Brudzinski negative, Babinski downgoing."),
    ("G06", "eponym-procedures", "[PATIENT_1] s/p Whipple procedure, later a Nissen fundoplication. Foley catheter removed. Swan-Ganz line out."),
    ("G07", "eponym-scores", "[PATIENT_1]: Apgar 8/9, Glasgow 15, Wells 1.5, Ranson criteria 2, Child-Pugh B, Gleason 3+4=7."),
    ("G08", "place-disease", "[PATIENT_1] with suspected Lyme disease after a tick bite; also tested for Rocky Mountain spotted fever and West Nile virus."),
    ("G09", "place-disease", "[PATIENT_1] returned from travel with fever; Ebola ruled out, testing for Zika and Coxsackie virus."),
    ("G10", "common-word", "[PATIENT_1] said she has lost hope and faith since the diagnosis but feels joy with her grandkids. Mood: will reassess in May."),
    ("G11", "common-word", "[PATIENT_1] will grant consent next visit. Mark the left knee before surgery. Bill insurance for the brace."),
    ("G12", "brand-drug", "[PATIENT_1] on Ozempic, Jardiance, Eliquis and Lipitor. Previously on Victoza; stopped due to GI upset."),
    ("G13", "brand-device", "[PATIENT_1] uses a Dexcom G7, Omnipod 5 and a ResMed AirSense 11 CPAP. Tandem t:slim was discontinued."),
    ("G14", "famous-person", "[PATIENT_1] asked whether his tremor is like Michael J. Fox's. Explained differences. Also asked about Christopher Reeve's injury."),
    ("G15", "numbers", "[PATIENT_1]: BP 120/80, HR 72, ratio 3/4, dose 5/325 Percocet q6h, PEEP 5, FiO2 40%. Room air sat 96%."),
    ("G16", "unit-words", "[PATIENT_1] moved from the ED to 4 West, then to the MICU. Seen by the Rapid Response team and Palliative Care."),
    ("G17", "year-holiday", "[PATIENT_1] was diagnosed in 2019 and had a flare around Christmas. Symptoms worse every winter."),
    ("G18", "provider-placeholder", "Discussed with [PROVIDER_1] (cardiology). [PATIENT_1] agrees with plan. [PROVIDER_2] to follow."),
    ("G19", "eponym-instrument", "Using a Doppler and a Snellen chart; [PATIENT_1] 20/40 OU. Ishihara plates normal. Weber midline, Rinne positive."),
    ("G20", "eponym-syndrome", "[PATIENT_1] with Down syndrome, Asperger features, and Tourette tics. Lives with [RELATIVE_1]."),
]

LEAK = [  # (id, trap, text) — the same kinds of words, but now they ARE identifiers
    ("H01", "surname=eponym", "Mr. Parkinson, 71M, has Parkinson's disease. On carbidopa-levodopa. Tremor stable."),
    ("H02", "surname=eponym", "[PATIENT_1] lives with her husband Tom Graves, who manages her Graves disease meds."),
    ("H03", "name=common-word", "Daughter Hope says [PATIENT_1] has been more confused since Tuesday. UA ordered."),
    ("H04", "name=common-word", "[PATIENT_1]'s son Will Grant called asking about discharge timing."),
    ("H05", "name=common-word", "Spoke with [PATIENT_1]'s sister, May Brown, who is the health care proxy."),
    ("H06", "place=disease-place", "[PATIENT_1] lives in Old Lyme, Connecticut, and found the tick in her yard."),
    ("H07", "famous-name-as-patient", "Patient Michael Fox, 45M, presents for tremor evaluation. Not the actor."),
    ("H08", "eponym+name", "[PATIENT_1] s/p Whipple; surgeon notes wife Linda Whipple will do drain care."),
    ("H09", "brand+name", "[PATIENT_1] on Ozempic; pharmacy tech Jordan Ellis called about prior auth for patient."),
    ("H10", "first-name-only", "Lou says the twitching started after his fall. [PATIENT_1] is 58 and a former roofer."),
    ("H11", "nickname", "Pt prefers to be called Sunny. [PATIENT_1] has Hashimoto's and Raynaud's."),
    ("H12", "initials+dob", "J.K.M., DOB 4/2/1950, seen for Crohn's flare. On Humira."),
]

CASES = [(i, "clean", t, x) for i, t, x in CLEAN] + [(i, "leak", t, x) for i, t, x in LEAK]


def _long():
    """Long notes (8 snippets): clean = 8 clean traps; leak = 7 clean traps + 1 leak."""
    import random
    rnd = random.Random(11)
    body = [t for _, _, t in CLEAN]
    out = []
    for i in range(20):
        out.append((f"GL{i+1:02}", "clean", "long-traps", "\n\n".join(rnd.sample(body, 8))))
    for lid, trap, leak in LEAK:
        snips = rnd.sample(body, 7)
        snips.insert(rnd.randrange(8), leak)
        out.append((f"HL{lid[1:]}", "leak", trap, "\n\n".join(snips)))
    return out


LONG_CASES = _long()
