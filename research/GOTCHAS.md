# De-identification gotchas for clinical text

What counts as PHI and what doesn't, with edge cases. Built from the annotation
guidelines and published error analyses (2026-10-26). Goal: stop our Sage check
from flagging things like "Lou Gehrig's disease" while still catching real leaks.

Verdicts assume our working standard: **HIPAA Safe Harbor, plus doctor names
removed** (we strip them anyway). Where the big corpora are stricter (i2b2
2014 tags every age and year), that's noted in the table.

## Sources (short names used below)

| Short name | What it is | URL |
|---|---|---|
| HHS | HHS/OCR 2012 de-id guidance, Safe Harbor FAQ §3.x | https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html |
| i2b2-06 | Uzuner, Luo, Szolovits 2007 (i2b2 2006 task) | https://pmc.ncbi.nlm.nih.gov/articles/PMC1975792/ |
| i2b2-14 | Stubbs & Uzuner 2015, 2014 corpus guidelines (Appendix A) | https://pmc.ncbi.nlm.nih.gov/articles/PMC4978170/ |
| n2c2-16 | Stubbs, Filannino, Uzuner 2017, psychiatric notes (CEGS N-GRID) | https://pmc.ncbi.nlm.nih.gov/articles/PMC5705537/ |
| deid | Neamatullah 2008, PhysioNet deid tool + gold standard | https://pmc.ncbi.nlm.nih.gov/articles/PMC2526997/ |
| MIMIC | MIMIC-III `[** **]` tags; MIMIC-IV-Note `___` | https://pmc.ncbi.nlm.nih.gov/articles/PMC4878278/, https://physionet.org/content/mimic-iv-note/2.2/ |
| MEDDOCAN | Spanish 2019 guidelines (29 types) | https://github.com/PlanTL-GOB-ES/SPACCC_MEDDOCAN |
| DEDUCE | Dutch rule-based de-id + lookup lists | https://github.com/vmenger/deduce |
| SEPR | Stockholm EPR PHI corpus (Swedish) | https://pmc.ncbi.nlm.nih.gov/articles/PMC2895734/ |
| GeMTeX | German GraSCCo_PII guideline v2, 2025 (most explicit "not PHI" list) | https://zenodo.org/records/15747389 |
| NorSynth | Norwegian NorSynthClinical-PHI | https://aclanthology.org/2021.nodalida-main.22.pdf |
| Yang15 | Yang & Garibaldi 2015, i2b2 2014 winner, error analysis | https://eprints.whiterose.ac.uk/id/eprint/108935/1/I2B2_PHI_JBI_2015.pdf |
| Dern17 | Dernoncourt 2017 (NeuroNER) hard cases | https://arxiv.org/pdf/1606.03475 |
| Liu17 | Liu 2017 RNN+CRF errors | https://pmc.ncbi.nlm.nih.gov/articles/PMC5705329/ |
| Philter | Norgeot 2020 | https://www.nature.com/articles/s41746-020-0258-y |
| Ferr12a | Ferrández 2012, 5 tools on VA notes | https://pmc.ncbi.nlm.nih.gov/articles/PMC3445850/ |
| Ferr12b | Ferrández 2012, person-name FP filter | https://aclanthology.org/W12-2408.pdf |
| Hart20 | Hartman 2020 (Google) customization errors | https://pmc.ncbi.nlm.nih.gov/articles/PMC6993314/ |
| Carrell13 | "Hiding in plain sight" leak study | https://pmc.ncbi.nlm.nih.gov/articles/PMC3638183/ |
| Pal26 | Palacios 2026, 8 LLMs vs TiDE at Texas Children's | https://arxiv.org/abs/2608.17051 |
| Agha25 | Aghakasiri 2025, LLM over-redaction impact | https://arxiv.org/pdf/2509.14464 |
| RedactOR | Oracle 2025 LLM de-id | https://arxiv.org/abs/2505.18380 |
| Land25 | Landes 2025 | https://arxiv.org/pdf/2506.12674 |

## The big picture first

- **Whose identifiers.** Safe Harbor covers the patient and their relatives,
  employers and household members. HHS §3.8: "There is no explicit requirement
  to remove the names of providers or workforce members." Names of anyone else
  (a celebrity, an author, the person a disease is named after) are not the
  patient's identifiers.
- **Only identifiers "recognizable as an identifier"** must go (HHS §3.10). A
  stand-alone "Newark, NJ" with no link to the patient "may be retained".
- **Ambiguity is the core problem.** HHS's own example: "is 5/97 a date or a
  ratio?" (§3.10). i2b2-06 made it worse on purpose: they swapped some surrogate
  names for "medical terms ... such as diseases, treatments, and medical test
  names". deid seeded its gold standard with "Wilson's disease" and
  "Parkinson's tremor" as hard cases.
- **Over-redaction has a cost.** In LLM de-id, 70–80% of sampled
  over-redactions changed clinical content that doctors rated high impact
  (Agha25). Drug names, doses and "stop" in "stop smoking" got removed.
- **Most real misses are false negatives, not false positives.** In Yang15,
  70% of errors were misses. Bias toward flagging when a span really could
  be the patient, but don't flag things that can't be.

## 1. Eponyms: diseases, signs, tests, scores, procedures, devices

Rule: a person's name used as the name of a disease, sign, test, score,
procedure, instrument or device is a medical term, not PHI. The pattern:
name + `'s` / `disease` / `syndrome` / `sign` / `test` / `score` / `maneuver` /
`procedure` / `valve` / `catheter` / `clinic`. GeMTeX §5.2 says it outright:
"Eponyms of scales, diagnoses, procedures etc. should be ignored (but may be
wrongly marked by automation)". DEDUCE ships a 22,512-entry eponym list that
cancels any name match inside it. It contains "Lou Gehrig". Meystre 2014
reclassified 112 eponyms as non-PHI; annotators agreed only 74% on them vs
93% on real names.

| Example | PHI? | Rule / source |
|---|---|---|
| Lou Gehrig's disease | No | Eponym. In DEDUCE's eponymous-disease list |
| Parkinson's disease, Parkinson's tremor | No | deid seeded it as a hard case |
| Wilson's disease, Huntington's disease | No | deid; i2b2-06 names "Huntington" as name-or-disease |
| Alzheimer's clinic | No | Hart20 example |
| Achilles reflex, Guyon's canal | No | Ferr12b: "most errors" of pattern tools were eponym FPs |
| Epley maneuver | No | Ferr12b. **But** "Mr. Epley" is PHI |
| Gleason 3+4, Bruce protocol, Apgar 9/9 | No | Land25 (Gleason), Hart20 (Bruce). Score digits are not dates |
| Barthel score, Glasgow Coma Scale 15, Rutherford stage | No | GeMTeX §5.2 |
| Foley catheter, Swan-Ganz, Holter monitor | No | Hart20 (Foley), Meystre 2014 (Holter) |
| St. Jude valve, Carpentier-Edwards valve | No | Hart20; i2b2-14: "No need to label names of devices" |
| Hartmann procedure, Whipple, Nissen fundoplication, Pfannenstiel incision | No | GeMTeX (Hartmann), Meystre (Pfannenstiel) |
| Factor V Leiden, von Willebrand factor | No | GeMTeX §5.2. "Leiden" is a city here, also not PHI |
| Down syndrome, Crohn's, Hodgkin, Bell's palsy, Tourette's | No | DEDUCE list. **Exception:** MEDDOCAN tags "Síndrome de Down" as OTHER patient info (risk-averse outlier) |
| Wernicke encephalopathy, Sudeck's atrophy | No | GeMTeX §5.2 |
| Lynch syndrome, Pfeiffer syndrome | No | DEDUCE drops "Lynch" and "Pfeifer" from its surname list (likely for this reason) |
| "Dr. Parkinson saw Mr. Crohn" | **Yes** | A title or a person role makes it a person. Same surname as a disease doesn't protect it |
| "Patient Alice Hodgkin, Hodgkin lymphoma" | Name: **yes**. Disease: no | Judge each mention by its role |

## 2. Drug, device and brand names

| Example | PHI? | Rule / source |
|---|---|---|
| Lipitor, Keppra, Humira, Ozempic | No | Medical terms. Philter keeps them on its allow-list. LLMs over-redact them (Agha25, Pal26) |
| Drug names inside patient-name lists | n/a | Philter found drug names stored as patient names in hospital DBs. Don't trust name lists blindly |
| Medtronic pump, Dexcom G7, Abbott | No | Brand/maker. MEDDOCAN: "brands and models are kept" (it says this of cars) |
| "pump serial # 4712198", "model # 5435" | Serial: **yes**. Model: no | Safe Harbor (M) device serials. Dern17 |
| "TDK", "Audiovox", "BrightPoint" | Context | Yang15 (TDK misread as PHI); Dern17 (as employers, they ARE PHI) |
| Toyota Camry | No | MEDDOCAN. Plate number or VIN: **yes** |

## 3. Names that are common words

Rule: a common word is a name only when it works as a person in the sentence.
Cues: a title (Mr., Dr., RN), a first+last pattern, "Last, First", a role
word (wife, son, friend, nurse), a possessive pointing at a person, or the
subject of "reports/denies/states". deid only removes an "ambiguous" name
(one that is also a dictionary word) when such cues are present. Philter
dropped 855 words from its name list ("new, walks, knee, home, child") and
found 16,095 names that were also medical terms or common words.

| Example | PHI? | Rule / source |
|---|---|---|
| "will follow up", "WILL" in caps | No | deid top FP: "WILL (5)" |
| "Will is her son", "son Will" | **Yes** | Role word |
| "hope to discharge" / "daughter Hope visited" | No / **Yes** | Role word |
| "BP rose to 160" / "Rose Martinez" | No / **Yes** | First+last pattern |
| "bill sent to insurance" / "goes by Bill" | No / **Yes** | deid, Ferr12b: nickname "Bill" missed |
| "grant-funded program" / "Dr. Grant" | No / **Yes** | Title |
| "joy, faith, penny" as words | No | Plain words |
| "skin brown", "GRAY matter", "WALKER", "cutter" | No | Ferr12a: BROWN, GRAY, WALKER, CUTTER flagged by rule tools |
| "White fluid found" / "Patient John White" | No / **Yes** | Philter's own example |
| "Young adult", "King-Devick test", "Green stool" | No | Plain words / eponym |
| "seen in May" | **Yes, as a DATE** | Month of a patient event (HHS §3.3). Not a name. Pal26 flags "May" as a scoring hazard |
| "May Chen" | **Yes, as a NAME** | First+last |
| "saw Guy in PT", "Strong to cover" | **Yes** | Hart20: 9 of 14 name misses were dictionary words |
| "Chase", "talbot", "ray", "West" (son (West)) | **Yes** in person context | Ferr12b, Yang15, Dern17 |
| "Yawn", "Morrow" (staff surnames) | **Yes** | n2c2-16 |
| "DRS. RIGHT AND SIGNS", "Ettrent Can" | **Yes** | i2b2-06 surrogates built to collide with words |
| Dutch: Bakker, Visser, Mulder, de Vries; Arts (=doctor), Lever (=liver), Been (=leg) | Context | DEDUCE keeps job-word surnames, drops body-part ones |
| German: "Tony Fuchs", "Caroline Wolf" | **Yes** | GeMTeX: animal-word surnames must be caught |
| "awoke", "Interesetd" | No | Hart20: verb and typo flagged as names |
| ALL-CAPS headers, sentence-initial words | No (by itself) | Philter: POS tagger read caps as proper nouns |

## 4. Place names inside medical terms

No guideline lists these. They follow from the HHS rule: only geography tied
to the patient (address, city, county, ZIP) is an identifier.

| Example | PHI? | Rule / source |
|---|---|---|
| Lyme disease, West Nile virus, Ebola, Marburg, Zika, Lassa, Coxsackie, Norwalk, Hendra | No | Disease names. Not the patient's location |
| Rocky Mountain spotted fever, Spanish flu, German measles, Japanese encephalitis | No | Same |
| Stockholm syndrome, Mediterranean diet, Boston Bowel Prep Scale, New York Heart Association class III | No | Same |
| Factor V Leiden, Ludwig's angina | No | Eponym/place in term |
| "returned from a trip to Lyme, CT" | **Yes** | Now a place the patient was |
| "lives in Coxsackie, NY" | **Yes** | Patient's town (city is below state) |
| "travel to Liberia" (country) | No under Safe Harbor | States and countries are allowed. i2b2-14 tags them; MEDDOCAN tags PAIS |
| "Newark, NJ" alone, unclear link | No | HHS §3.10 scenario 2: "may be retained" |
| Ethnic or nationality words ("Khazakhstani") | No under HIPAA | deid and MEDDOCAN remove ethnicity; GeMTeX, SEPR don't |

## 5. People: patient vs provider, initials, signatures, famous names

| Example | PHI? | Rule / source |
|---|---|---|
| Patient, relatives, employer, household names | **Yes** | Safe Harbor (A); HHS §3.8 |
| "Dr. Smith", "RN Jones" | Not required by HIPAA | HHS §3.8. But i2b2, MEDDOCAN, GeMTeX, MIMIC all remove them, and we do too |
| "Dr." / "MD" / "RN" / "Mr." | No | Titles are outside the span (i2b2-14, MEDDOCAN, NorSynth) |
| "attending", "Oberarzt", "charge nurse" | No | Role, not identity (GeMTeX) |
| Patient initials "KC reports...", "KCs depression" | **Yes** | HHS §3.2: initials are parts of names. Liu17: CRF found only 10 of 30+ "KC" |
| Signature/transcriber initials at the end ("arw/jt") | **Yes** | i2b2-14: "Annotate initials at end of documents" |
| Usernames "arw4", "entered by gsmith" | **Yes** | i2b2-14 USERNAME / DOCTOR |
| "Dear Harry and Yair", letter salutations | **Yes** | Dern17; Carrell13 found leaks in pasted letters |
| "RICO,HELEN U", "Dr. Xique, Olivia" | **Yes** | Yang15, n2c2-16: "Last,First" formats missed |
| Six-word name, partly removed | **Yes** (leftover parts) | Philter: only 3 of 6 words removed each time |
| Surname replaced, first name left | **Yes** | Carrell13 |
| Pet name ("her dog Biscuit") | Treat as **yes** | n2c2-16 notes include pet names; quasi-identifier |
| "big Taylor Swift fan", "read about Lou Gehrig" | No | Not the patient's identifier (HHS §3.8). Celebrity is not a relative |
| "his friend Epstein" | **Yes** | Dern17. A named person in the patient's life |
| "daughter of the state health minister" | **Yes** | Quasi-identifier. GeMTeX OTHER; MEDDOCAN tags "la ministra de Defensa" |
| Author names in citations ("per Smith et al. 2019") | No | GeMTeX |

## 6. Hospitals, units, rooms

| Example | PHI? | Rule / source |
|---|---|---|
| ICU, MICU, ER, ED, PACU, OR, cath lab, Cardiology, Radiology | No | i2b2-14 generic list; GeMTeX; SEPR ("Geriatriken" alone not tagged). NorSynth is the outlier |
| "Rafael Mount ED", "Bigelow C", "Paul-Langerhans-Station" | **Yes** | Named or unique unit (i2b2-14, GeMTeX) |
| Named hospital ("Sacred Heart", "MGH", "TCH", "BCM", "NPH") | **Yes** (with doctor names policy) | Not a HIPAA identifier by itself, but all corpora remove it. Pal26: 29% of Sonnet 4.6 misses were abbreviations like TCH. Yang15: "Sacred Heart" is also misread as non-PHI |
| "OSH" (outside hospital), "VA" (could be Virginia) | OSH: no. VA: context | i2b2-14; n2c2-16 |
| "MH", "ECF", "ENT", "OT", "HCS" | No | Generic acronyms (Ferr12a/b) |
| Building/campus names ("Mark Wallace Tower", "West Campus") | **Yes** | Pal26 |
| OR room codes ("LT OR", "WT MAIN OR") | **Yes** | Pal26: missed by models and humans |
| Room/bed "Room 254", "bed 3B", "Station 123" | **Yes** (strict) | i2b2-14 ROOM; GeMTeX. Not named in Safe Harbor; treat as "other unique code" |
| "Praxis Dr. Mustermann" (clinic named after a doctor) | **Yes** | GeMTeX |
| "Nutrition Clinic", "Alzheimer's clinic" | No | Generic service (Yang15, Hart20) |
| Company/school: "Harvard University", "Depew HS", "Dunkin Donuts"/"DD" | **Yes** when it's the patient's employer or school | i2b2-14 ORGANIZATION; Liu17 |
| "deli", "gas station", "hair salon" | No | Generic. n2c2-16 tagged them; i2b2-14 didn't |

## 7. Numbers: doses, vitals, scores vs IDs and contact numbers

| Example | PHI? | Rule / source |
|---|---|---|
| 120/80, BP 140/90 | No | Vital sign, not a date |
| "pain 1/10", "CVD 8-10", "NRS 10/10" | No | Ferr12a misread as dates; GeMTeX scores |
| "2/2 diabetes" (= secondary to) | No | i2b2-14 |
| "5/97" with no context | **Ambiguous** | HHS §3.10's own example. Flag only if it reads as a date |
| "76 mg" / "SpO2 76" / "76 years old" | No / No / No (<90) | RedactOR |
| "Quit at 38 y/o", "Died @ 52", "53RHM", "86F" | Age, <90: no under HIPAA | Dern17 (i2b2 tags them) |
| Tidal volume 450, "SVR 1200-1400", "VT 500" | No | deid: XXX-XXXX not a phone after SVR, VT, Tidal Volume |
| Lab accession "Specimen: 38:Z8912708G" | **Yes** | Dern17. Unique ID |
| 7-digit number at the top of every note | **Yes** (MRN) | Hart20 |
| "MC # 0937884Date", "JOB#000201" | **Yes** | Glued tokens (Dern17, Ferr12a) |
| Pager "pg 4-1234", "x549", Voalte numbers | **Yes** (strict) | i2b2-14: pagers are PHONE. Pal26 misses. deid calls provider pagers non-HIPAA but removes them |
| Clinical trial record number | **Yes** | HHS §3.5 |
| Last 4 of SSN | **Yes** | HHS §3.2: parts of identifiers are identifiers |
| Barcode, unsalted hash of a name/MRN | **Yes** | HHS §3.5 |
| Our `[MRN_1]`, MIMIC `[**Known lastname 25925**]`, MIMIC-IV `___` | No | Placeholders. Already removed |
| ICD-10 codes, TNM "T2N0M0", "UICC 2024", "NB2004" | No | GeMTeX |
| House number alone ("lives at 14") | **Yes** | Part of street address. Wiest 2024 warns blind number redaction eats lab values |
| ZIP 3 digits (e.g. "021") | No, unless one of the 17 small ones | HHS §3.1: 036, 059, 063, 102, 203, 556, 692, 790, 821, 823, 830, 831, 878, 879, 884, 890, 893 → 000 |

## 8. Dates, times, holidays, years

Safe Harbor: every date element smaller than a year, for a date tied to the
patient, is PHI. Year alone is fine (HHS §3.3: "January 1, 2009" → "2009").
Lab dates count (§3.4). The corpora disagree on the rest; see the last column.

| Example | PHI (Safe Harbor)? | Others |
|---|---|---|
| "03/14/2024", "March 14", "14 March" | **Yes** | All |
| "admitted in March", "seen in May" | **Yes** (month) | All |
| "2019", "CABG 1996" | No | i2b2-14, n2c2-16, MEDDOCAN, GeMTeX tag years; DEDUCE doesn't |
| "'92", "the 90's", "late 60s", "in 08" | No (year/decade) | i2b2-14 tags them. "60s" may be an age (n2c2-16) |
| Weekday ("on Thursday") | No by itself | i2b2-14, MEDDOCAN tag; SEPR, NorSynth, GeMTeX don't. MIMIC keeps weekdays |
| "Christmas", "Thanksgiving", "Ramadan", "night before Christmas" | **Yes** (implies month/day) | i2b2-14, MEDDOCAN, deid, MIMIC tag. Misspelled "Christams" too (n2c2-16) |
| Season ("spring", "Fall '02") | Borderline: treat as **yes** with a year | i2b2-14 tags; NorSynth doesn't |
| Time of day "1:00 pm", "0800", "q8h" | No | i2b2-14: "Do not include time of day". Pal26: LLMs over-redact times |
| Relative: "3 days ago", "POD 2", "hospital day 5", "x2 weeks", "for 10 years" | No | GeMTeX explicit; DEDUCE treats "sinds 10 jaar" as duration |
| Dates years in the future ("2142-11-30", "2091") | No | MIMIC shifts dates into the 2100s. A shifted date is a placeholder |
| A real date left inside a shifted note | **Yes** | Carrell13: it stood out and gave itself away |
| Dates on medical events not about this patient ("FDA approved in Dec 2019") | No | Not "directly related to an individual" (HHS) |
| "M-F", "Su T R" (schedule days) | No | n2c2-16 notes them as date-like |
| Broken across lines "April 12, ... 2091" | **Yes** | Yang15 |

## 9. Ages

| Example | PHI? | Rule / source |
|---|---|---|
| "88-year-old", "age 45" | No (Safe Harbor) | HHS: only ages over 89. i2b2-14 and MEDDOCAN tag every age |
| "92-year-old", "nonagenarian", "centenarian", "100-åringen" | **Yes** | Recode as 90+ |
| Birth year that implies 90+ ("born 1931", seen 2026) | **Yes** | HHS §3.3: year too, if it implies age |
| "daughter, 8", "3 weeks old", "teen" | No | Under 90. i2b2 tags kids' ages; GeMTeX skips relatives' ages |
| "30 days" (duration) | No | Ferr12a misread as age |
| "smoked 20 years", "20 pack-years" | No | Duration, not age (DEDUCE) |

## 10. Contacts, web, codes

| Example | PHI? | Rule / source |
|---|---|---|
| Phone, fax, email, URL, IP | **Yes** | Safe Harbor D–F, N, O |
| Generic site "uptodate.com", "cdc.gov" | No | Not about the patient |
| Clinic main line on a letterhead | Strict **yes** | Narrows to a site |
| "a.jd" style user IDs | **Yes** | GeMTeX NAME_USERNAME |

## 11. Quasi-identifiers ("actual knowledge")

Safe Harbor also fails if you know the rest could identify the person (HHS
§3.6). HHS examples: "current President of State University", a relative who
would recognize a complex case, a multiple birth covered by the press.

| Example | PHI? | Rule / source |
|---|---|---|
| "Executive Vice President of the state university" | **Yes** | HHS §3.10 scenario 1 |
| "head coach of the [PLACE_1] varsity team" | **Yes** | Our RESULTS.md false block was arguably right |
| "the last alpine innkeeper in the valley" | **Yes** | GeMTeX OTHER |
| "mother of octuplets" | **Yes** | HHS §3.6 example 3 |
| Plain job: "glazier", "CPA", "teacher", "retired" | Mostly no under HIPAA | i2b2/MEDDOCAN tag professions; flag only if unique or paired with a small place |
| Rare disease + small town + age | **Yes** together | HHS actual knowledge. Judge the combination, not each word |
| Tattoo ("Donald Duck tattoo on left arm") | Borderline | MEDDOCAN tags it as OTHER |
| Tornado, crash, fire "in the news" | **Yes** if tied to a date or place | deid: "trailer was blown away by a tornado the night before Christmas" |
| Sex, marital status, religion | No under HIPAA | MEDDOCAN tags sex and religion; GeMTeX, SEPR don't |
| Full-face photo, "see attached photo" | Photo itself **yes**; the reference no | Safe Harbor (Q) |

## 12. Format, OCR and language

| Example | PHI? | Rule / source |
|---|---|---|
| Misspelled names "Willaim", "hass" | **Yes** if a person | deid. Typos defeat lists |
| Lowercase names "ACT : rosenberg" | **Yes** | Dern17 |
| Glued tokens "Results02/20/2087", "1/20/71Total" | **Yes** (date inside) | Dern17, Liu17 |
| Garbled "DT: 01/19/:0" | **Yes** | Dern17 |
| "teh late 60s" | Treat as date/age | Dern17 |
| Non-English names, "Sr./Dña.", "van de", "von" particles | Particles part of name | MEDDOCAN, DEDUCE |
| German "Morbus Sudeck", Dutch "ziekte van Crohn" | No | Eponyms in other languages |
| Abbreviations that look like names/places: MAE, LOS, ADA, BPH, PERL, "MA" | No | deid top FPs; i2b2-06 (BPH as hospital) |
| Template field labels "Name:", "DOB:", "Sex:" | No | MEDDOCAN G2: don't tag the label, tag the value |

## Where the standards disagree (pick one and say it)

| Item | HIPAA Safe Harbor | i2b2 2014/2016 | MEDDOCAN | GeMTeX | DEDUCE |
|---|---|---|---|---|---|
| Doctor names | Not required | Yes | Yes | Yes | Yes |
| Ages under 90 | No | Yes | Yes | Patient only | Yes |
| Year only | No | Yes | Yes | Yes | No |
| Weekday | No | Yes | Yes | No | No |
| Holiday | Yes (implies date) | Yes | Yes | Yes | No |
| Time of day | No | No | No | No | No |
| Generic unit (ICU) | No | No | Unclear | No | No |
| Profession | Only if unique | Yes | Yes | Patient only | No |
| Sex / religion | No | No | Yes | No | No |
| Eponyms | No | Not stated | Not stated (one positive example) | No, explicit | No, explicit list |

---

## Draft instructions for a classifier

Paste-ready. Assumes Safe Harbor plus doctor names. Placeholders look like `[NAME_1]`.

```
You check clinical text that was already de-identified. Flag only REAL leftover
identifiers of the patient, their relatives, household or employer, or of staff.

NOT identifiers (never flag):
1. Placeholders like [NAME_1], [DATE_2], [**...**], ___ . They are already removed.
2. Eponyms: a person's name used as a disease, sign, test, score, procedure,
   device or drug: Lou Gehrig's disease, Parkinson's, Crohn's, Down syndrome,
   Apgar, Gleason, Glasgow, Epley maneuver, Foley, Swan-Ganz, St. Jude valve,
   Whipple, Holter, Barthel, Bruce protocol, Factor V Leiden.
3. Place names inside disease or term names: Lyme disease, West Nile, Ebola,
   Rocky Mountain spotted fever, Coxsackie, Stockholm syndrome, NYHA class.
4. Drug, device and company brand names (Lipitor, Humira, Medtronic, Dexcom).
5. Common words used as words: will, hope, rose, bill, grant, mark, joy, faith,
   penny, brown, green, white, young, king, guy, strong.
6. Famous people not in the patient's life (celebrity, study author).
7. Measurements: doses (50 mg), vitals (120/80), scores (pain 7/10, GCS 15),
   lab values, durations (3 days, 20 pack-years), times (0800), q8h, POD 2.
8. Year alone (2019), decades (the 90s), relative dates (3 days ago).
9. Ages 89 and under. Countries and US states. Field labels (Name:, DOB:).
10. Generic units and roles: ICU, ER, OR, cath lab, Cardiology, attending,
    "outside hospital". Titles alone: Dr., MD, RN, Mr.

ARE identifiers (flag):
11. A name or initials acting as a person: after a title (Mr. Epley,
    Dr. Grant), first+last (Rose Chen), "Last, First", after a role word
    (son Will), as who reports/denies, in a signature or salutation.
    Lowercase or misspelled too. "Mr. Parkinson" is a name.
12. Any day or month of a patient event: 03/14, "in May", Christmas.
    Ages 90+ (nonagenarian), or a birth year implying 90+.
13. Street, house number, city, county, town, ZIP beyond 3 digits. A town
    the patient lives in or visited, even if it is also a disease name.
14. Phone, fax, pager, email, URL, IP, MRN, account, SSN (even last 4),
    license, plate, device serial, accession or trial numbers, barcodes.
15. Named hospitals, clinics, buildings, wards, rooms, beds, OR codes, and
    their abbreviations (TCH, MGH). The patient's employer or school.
16. A detail that points to one person: a unique job (president of X
    university), a news event, rare disease + small town + age.

When a token could be either (May, Will, 5/97), decide by its role in the
sentence. If it really could be the patient's name or date, flag it.
```
