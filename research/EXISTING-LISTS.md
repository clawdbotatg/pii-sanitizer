# Existing de-id "gotcha" lists (2026-10-26)

Question: has anyone already written down what looks like PHI but isn't
(eponyms like "Lou Gehrig's disease", drug brands, scores, departments,
names that are also words), and what PHI gets missed? Sage flagged
"Lou Gehrig's disease" as a name, so we want a list or a skill file.

**Short answer:** yes, in pieces. No single list covers it. Old rule-based
tools (Philter, PhysioNet deid, DEDUCE, CRATE, CliniDeID) all ship
"not PHI" lists, because they hit the same problem. Cloud services and LLM
guardrails ship none; they give you an allow-list hook and stop there.
Nobody ships a clinical-score list or a "PHI that gets missed" list.

Downloaded copies (untrusted data, not in the repo):
`/private/tmp/claude-501/-Users-austingriffith-clawd-clawd-harness-projects-clawd-research/5feac2f7-db65-44c5-a0c8-d0e7eb2fff67/scratchpad/lists/`

## 1. Philter (UCSF) — the known lead

https://github.com/BCHSI/philter-ucsf · BSD-3 · last commit 2023-09-29.
Paper: Norgeot et al. 2020, https://www.nature.com/articles/s41746-020-0258-y

### What ships

| File | Size | What it is |
|---|---|---|
| `filters/whitelists/whitelist_plus_fps_091718_nonames.json` | 195,253 words | Safe words. Built from UMLS/SNOMED/MeSH terms, med abbreviations, top 20k English words. All Census/SSA names removed, then ~16k names that are also medical/English words added back. |
| `filters/blacklists/firstnames_minus_fps.json` | 97,014 | First names, minus known false positives |
| `filters/blacklists/lastnames_minus_fps.json` | 161,470 | Last names, minus known false positives |
| `filters/regex/safe/*_safe.txt` | 133 regexes | Phrase-level "this is safe" patterns |
| `filters/regex/salutations/`, `organizations/`, `regex_context/` | ~40 regexes | Name/hospital context patterns (PHI side) |

All JSON files are `{"word": 1}` dicts, lowercase.

Safe regex samples (one regex per file):

```
parkinson_safe.txt     \b(?i)parkinson(\')?(s)?\sdisease\b
crohns_disease_safe    \b(?i)crohn\'s\sdisease\b
down_syndrome_safe     \b(?i)down(\'s)?\ssyndrome\b
may_safe               \b(?i)may\s(also|have|need|be)\b
young_safe             \b(?i)young\s(adult(s)?|age)\b
bee_safe               \b(?i)((honey)\sbee|bee\s(venome|sting))\b
pap_safe               \b(?i)pap\s(smear(s)?|result(s)?)\b
hospital_safe          ~50 department names: Emergency Department, Intensive Care Unit,
                       Internal Medicine, Physical Therapy, Radiology, Infirmary ...
medical_safe.txt       \b(?i)medi\-cal\b      (just this one)
```

Only 4 eponym phrases are regexes: Parkinson's disease, Crohn's disease,
Down syndrome, Barrett's esophagus.

Spot checks (my lookups):

| Word | Whitelist | First-name list | Last-name list |
|---|---|---|---|
| hope, will, mark | yes | yes | yes |
| may | yes | no | no |
| foley, apgar, glasgow, coumadin, lasix, tylenol, romberg, kernig | yes | some | some |
| parkinson, hodgkin, babinski, cushing, crohn | **no** | no | **yes** |
| gehrig, lou, wells, graves, addison, wilson, murphy, huntington, turner, paget | **no** | **yes** | **yes** |
| alzheimer, kaposi, raynaud, marfan | no | no | no |

### How precedence works

Config `configs/philter_delta.json` is an ordered list of 313 filters.
Code: `philter_ucsf/philter.py`, `get_exclude_include_maps`.

1. Filters run in order. **First match on a span wins.** A "safe" hit
   (include) blocks any later PHI hit on the same span, and vice versa.
2. Order: UCSF safe regexes → `safe/*` regexes → PHI regexes (dates, IDs,
   salutations…) → **name blacklists (only for words POS-tagged `NNP`)** →
   name context regexes → **whitelist** → numbers → initials.
3. `regex_context` filters are the exception: they override safe spans.
4. **Default is redact.** Any word not matched as safe is PHI.

So "Lou Gehrig's disease": no safe regex, "Gehrig" is NNP and in the
last-name blacklist, blacklist runs before the whitelist → redacted.
Philter would make the same mistake Sage did.

Fork: philter-lite (https://github.com/SironaMedical/philter-lite, BSD-3,
2026-05-19) packs the same lists into one `filters/set.toml`.

## 2. PhysioNet deid (Neamatullah 2008)

https://physionet.org/content/deid/1.1/ · code GPL-2 (`COPYING`), project
page lists **Open Data Commons Attribution 1.0**. Files dated 2019-04-12.
Paper: https://doi.org/10.1186/1472-6947-8-32. Python port:
https://github.com/GEMINI-Medicine/pyDeid (MIT label over the same lists).

Files: `https://physionet.org/files/deid/1.1/dict/<name>` and `/lists/<name>`.
PhysioNet is slow (one 630 KB file took ~2 min).

| File | Lines | What it is |
|---|---|---|
| `dict/sno_edited.txt` | 175,313 | SNOMED-derived word list (UPPERCASE). Has BABINSKI, GEHRIG, GEHRIGS, PARKINSON. SNOMED license applies. |
| `dict/common_words.txt` | 49,669 | Common English words |
| `dict/commonest_words.txt` | 5,127 | Very common words |
| `dict/medical_phrases.txt` | 28 | Eponym phrases: Bell's palsy, Down Syndrome, Wilson's disease, Dressler syndrome, Fournier's gangrene, Lambert-Eaton syndrome, Morison's pouch, Riker scale, St. Jude valve, swan ganz, West Nile Virus |
| `dict/notes_common.txt` | 66 | Words always safe: CANCER, CARDIOLOGY, PSYCHIATRY, TRAUMA, DR, PT … |
| `lists/last_names_ambig.txt` | 7,298 | **Last names that are also words.** Has BABINSKI, GEHRIG, HODGKIN, PARKINSON, WELLS, HOPE, MARK, MAY, WILL, FOLEY, GLEASON, BECKWITH, MAFFUCCI |
| `lists/last_names_unambig.txt` | 81,497 | Last names that are only names |
| `lists/female_names_ambig.txt` / `male_names_ambig.txt` | 616 / 419 | First names that are words: HOPE, MARK, MAY, WILL, AMBER, AUGUST, ART |
| `lists/locations_ambig.txt` | 136 | Places that are words: HOPE, NORMAL, MOBILE, FOLEY, PHOENIX, READING, UNION |
| `lists/company_names_ambig.txt` | 18 | Pfizer, Wyeth, CVS, Oracle, Dell … |
| `lists/stripped_hospitals.txt`, `doctor_*_names.txt` | 143 / ~300 | Boston-specific (MIMIC era) |

How it's used (`deid.pl`): an **unambiguous** name is PHI on sight. An
**ambiguous** name is PHI only with context: a title (Dr., Mr.), a
first+last pair, or a name indicator. Common-word checks (`isCommon`) also
block it. This is the right model for "Lou Gehrig": ambiguous, and no
name context around it except "Lou".

## 3. Other de-id tools

| Tool | URL | License | Last commit | Lists shipped | Eponyms / drugs? | Reusable? |
|---|---|---|---|---|---|---|
| **CRATE** (Cambridge) | https://github.com/ucam-department-of-psychiatry/crate | GPL-3 | 2026-08 | `crate_anon/anonymise/eponyms.py`: 535 eponym surnames, each with its disease in a comment ("Lou Gehrig", "Parkinson", "Wells", "Bell"). Removed from the name list before scrubbing. | Eponyms yes | GPL; easy to extract |
| **DEDUCE** (Dutch) | https://github.com/vmenger/deduce | GPL-3 | 2025-08 | `src/whitelist/lst_eponymous_disease` 226 ("Lou Gehrig", "Non-Hodgkin", "Wolff-Parkinson-White"); `lst_eponymous_single` 760; `lst_medical_term` 6,939 (Dutch); `exceptions.txt` per name list (first names 195, surnames 164) | Eponyms yes; drugs partly (Dutch) | GPL; plain txt. Best-designed whitelist of all |
| **CliniDeID** (Clinacuity) | https://github.com/Clinacuity/CliniDeID | GPL-3 | 2023-08 | Lucene index `data/luceneIndex/eponyms/all` ~3,318 eponym tokens; `eponyms/conflicts` 70 (eponyms that are also common surnames: murphy, allen, jones, kelly, wilson, osler, whipple, romberg, trendelenburg, doppler, pap, guyon) | Eponyms yes, biggest; covers gehrig, wells, apgar, gleason, glasgow, foley | GPL; binary, pull with `strings` |
| Stanford TiDE | https://github.com/susom/tide | Apache-2 (badge) | 2026-03 | `umls_minus_provider.csv` 96k, `umls_token_600m.csv` 617k as whitelist; `wordIgnore.txt` 344 | Via UMLS | UMLS license applies |
| Phileas (philterd) | https://github.com/philterd/phileas | Apache-2 | 2026-10 | `city-common-words.txt` 1,282 (cities that are words), first names 30k, hospitals 335 | No | Yes |
| NLM Scrubber | https://lhncbc.nlm.nih.gov/scrubber/ | US gov, none stated | 2019 | One packed binary, no readable lists | ? | No |
| MIST (MITRE) | https://sourceforge.net/projects/mist-deid/ | BSD | 2014 | Model-based; download blocked, not checked | ? | n/a |
| nedap deidentify | https://github.com/nedap/deidentify | MIT | 2023-11 | 702 Dutch institutions; rest from DEDUCE | via DEDUCE | MIT code, GPL lists |
| Presidio | https://github.com/microsoft/presidio | MIT | 2026-10 | No lists. `allow_list` / `deny_list` args, `MedicalNERRecognizer` (HF model) | No | Hook only |
| presidio-research | https://github.com/microsoft/presidio-research | MIT | 2026-10 | Fake-data inputs (3k names, 22k companies) | No | Test data only |
| scrubadub | https://github.com/LeapBeyond/scrubadub | Apache-2 | 2023-09 | None; `disallowed_nouns={"skype"}` | No | Hook only |
| MedCAT / AnonCAT | https://github.com/CogStack/MedCAT | Apache-2 | 2025-07 (archived) | Model only, weights gated | No | n/a |
| robust-deid (OBI) | https://github.com/obi-ml-public/ehr_deidentification | MIT | 2022-06 | 545 med abbreviations (tokenizer) | No | Not useful |
| NeuroNER | https://github.com/Franck-Dernoncourt/NeuroNER | MIT | 2019-10 | None | No | n/a |
| medspaCy | https://github.com/medspacy/medspacy | MIT | 2026-06 | Negation/section rules only | No | Not useful |
| MIDRC Stanford/Penn | https://github.com/MIDRC/Stanford_Penn_MIDRC_Deidentifier | Apache-2 | 2025-11 | `frequent_hospitals_tokens.txt` 77 (Mercy, Permanente, Ochsner) | No | Yes, small |

## 4. Cloud services

None ships a false-positive list. All say "set a threshold, add review".

| Service | Doc | What it says |
|---|---|---|
| Amazon Comprehend Medical DetectPHI | https://docs.aws.amazon.com/comprehend-medical/latest/dev/textanalysis-phi.html | NAME = "all names mentioned". Only stated exclusion: named phone numbers (1-800-QUIT-NOW, 911). No allow list. Nothing on eponyms. |
| Google Sensitive Data Protection (DLP) | https://docs.cloud.google.com/sensitive-data-protection/docs/creating-custom-infotypes-rules | Exclusion rules: dictionary, regex, or `excludeInfoTypes`, plus hotword proximity. Has `MEDICAL_TERM` and `FDA_CODE` infoTypes. You can drop PERSON_NAME hits that MEDICAL_TERM also matches, but it's not on by default. |
| Azure de-identification service | https://learn.microsoft.com/en-us/azure/healthcare-apis/deidentification/transparency-note | Favors recall (>95%). Their FP example: "allergic reaction to cat hair" → "*doctor* hair". Limits: misspellings, structured text without context, a patient unique by rare disease. Recommends surrogates. |
| Azure Language PII (`domain: phi`) | https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/how-to/adapt-to-domain-pii | `excludedValues` exact-match allow list (GA 2026-05). Empty by default. |
| John Snow Labs Healthcare NLP | https://nlp.johnsnowlabs.com/licensed/api/python/reference/autosummary/sparknlp_jsl/annotator/deid/deIdentification/index.html | Closed. Entity-level black/white lists and `ChunkFilterer` whitelist. No shipped word list found. |

## 5. LLM-era guardrails and prompts

| Item | URL | License | Gotcha list? |
|---|---|---|---|
| LLM Guard `Anonymize` | https://github.com/protectai/llm-guard | MIT | `allowed_names` / `hidden_names`, both empty by default |
| NeMo Guardrails sensitive data | https://github.com/NVIDIA/NeMo-Guardrails | Apache-2 | Entities + threshold only |
| Guardrails AI `detect_pii`, `guardrails_pii` | https://github.com/guardrails-ai/detect_pii | Apache-2 | No |
| Lakera Guard | https://docs.lakera.ai/docs/data-leakage-prevention | closed | Custom allow/deny lists; nothing medical |
| Anthropic "PII purifier" prompt | https://platform.claude.com/docs/en/resources/prompt-library/pii-purifier | docs | No FP examples; warns about spaced-out PII |
| OpenAI Privacy Filter model card | https://cdn.openai.com/pdf/c66281ed-b638-456a-8ce1-97e9f5264a90/OpenAI-Privacy-Filter-Model-Card.pdf | Apache-2 model | Lists failure modes (below), no list |
| DeID-GPT | https://arxiv.org/abs/2303.11032 | MIT | Prompt says redact anything that "might be a name". Would redact Lou Gehrig by design |
| LLMAnonymizer (Kather lab) | https://github.com/KatherLab/LLMAnonymizer | AGPL-3 | User writes prompts |
| arXiv 2608.17051 (institution-specific prompting) | https://arxiv.org/html/2608.17051 | paper | **Closest prior art.** Has explicit DO-NOT-REDACT lists (below) |

Prompt lines worth stealing (arXiv 2608.17051, quoted by the survey agent;
not re-checked by me):

- Precision prompt, don't redact: "(1) clock times, (2) lab/vital values,
  (3) medication doses (4) ages under 90, (5) relationship words,
  (6) clinical abbreviations". Plus: "when genuinely ambiguous and could
  identify a specific person, prefer to redact."
- Scrubber: "DO NOT REDACT: clock times, generic location descriptors (OR,
  PACU, ICU, Pod A)… clinical department TYPES without institution name,
  procedure codes, medication names, lab values, vital signs".
- Auditor: restore a placeholder only if it is "OBVIOUSLY" a medication,
  lab, diagnosis, anatomy term, abbreviation, vital, procedure or clock time.
  Never restore dates, person names, or specific institution names.

None of them mention eponyms.

## 6. Eponym sources

| Source | Count | License | Bulk download |
|---|---|---|---|
| Wikipedia: List of eponymous diseases / medical signs / fractures / surgical procedures / tests | ~920 terms parsed (557 / 287 / 41 / 32 / few) → ~1,000 surnames | CC BY-SA 4.0 | Easy: `https://en.wikipedia.org/w/index.php?title=List_of_eponymous_diseases&action=raw`. Wikitext, needs a parser. |
| Wikidata: items with "named after" (P138) a human plus a disease ID (DOID/ICD-10/MeSH…) | 838 raw rows → 509 terms where the person's surname is in the label | **CC0** | Easy, one SPARQL query. Needs light cleanup (has "Tasmania", "Eustachian tube"). Missed "Lou Gehrig's disease". |
| CliniDeID eponym index | ~3,318 tokens | GPL-3 | `strings` on a Lucene file |
| CRATE `eponyms.py` | 535 surnames | GPL-3 | One Python file |
| DEDUCE eponym lists | 226 + 760 | GPL-3 | Plain txt |
| LITFL Eponymictionary | 3,504 people, 7,921 terms (their count) | copyrighted site | No bulk download |
| Whonamedit? | ~7,000 (2014 figure) | copyrighted; **site offline since 2025**, Wayback only | No |
| MeSH | thousands of eponym-shaped descriptors (possessive dropped: "Parkinson Disease") | free, no license | https://www.nlm.nih.gov/databases/download/mesh.html; scripted fetch got an HTML page, needs a browser or FTP mirror. Lookup API caps at 50 results. |
| UMLS / SNOMED CT | largest | UMLS license (free, sign-up; SNOMED affiliate terms) | Yes after license |

**Measured overlap (my run):** of ~1,000 surnames pulled from the
Wikipedia eponym lists, **695 are in Philter's name blacklists** and 619 are
in PhysioNet deid's name lists (210 in its "unambiguous" list, so deid
would redact them on sight, e.g. Abercrombie, Bancroft). Only 163 are in
Philter's whitelist. Every name-list approach will hit eponyms unless an
eponym list is subtracted first. CRATE and DEDUCE do exactly that.

## 7. Drug name sources

| Source | Count | License | Download |
|---|---|---|---|
| FDA NDC `product.txt` | 27,344 unique Rx+OTC brand names; 6,191 substances | Public domain | https://www.accessdata.fda.gov/cder/ndctext.zip (11 MB, updated daily) |
| RxNorm Current Prescribable Content | ~all US Rx drugs | Public domain, **no login** | https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html (`RxNorm_full_prescribe_MMDDYYYY.zip`); API: https://lhncbc.nlm.nih.gov/RxNav/APIs/PrescribableAPIs.html |
| RxNorm full | larger | UMLS login | same page |

**Drug brands that are names (my run):** 164 one-word NDC brands are in
Philter's name lists. Worst offenders are birth-control pills named like
women: **Camila, Errin, Yasmin, Yaz, Skyla, Portia, Natazia, Ella, Sabina,
Contessa, Nikki, Abigale**. Also Bayer, Dove, Suave, Zeus, Soma, Terrell,
Senna, Saline. A Sage "name" tag may flag "started on Camila 0.35 mg".

## 8. Gotchas reported in papers and docs

**Looks like PHI but isn't**

- Eponym diseases/signs: Lou Gehrig's, Parkinson's, Hodgkin, Babinski,
  Achilles, Guyon, Bell's palsy (Philter, deid, CRATE, BioNLP 2012
  https://aclanthology.org/W12-2408.pdf).
- Devices/products: "St. Jude valve", "indwelling Foley", "Swan-Ganz",
  "Jackson-Pratt drain", "Medtronic" (BMC 2020 https://pmc.ncbi.nlm.nih.gov/articles/PMC6993314/).
- Scores/protocols: "Bruce Protocol", "Gleason", "Glasgow", "Apgar",
  "Riker scale", "Wells".
- Places in disease names: West Nile, Lyme, "Glasgow" (coma scale).
- Common words after a title: "Ms Mitchel **awoke**" → "awoke" tagged as
  a name (BMC 2020).
- Department / unit words: ER, ICU, PACU, "Pod A", "Internal Medicine".
- Ordinary words as names: "cat hair" (Azure), May (month), Hope, Will, Mark.
- Admin dates and company names that contain a surname ("Williams
  Insurance Co.") — OpenAI Privacy Filter benchmark.
- Named phone numbers: 1-800-QUIT-NOW, 911 (AWS).

**PHI that gets missed**

- Names that are words: "saw **Guy** in PT", "**Strong** to cover",
  Bill, Chase, Jane (BMC 2020, BioNLP 2012, Azure).
- Hospital abbreviations and building names: TCH, BCM, "Mark Wallace
  Tower", "West Campus", OR room codes, 4-digit pager numbers
  (arXiv 2608.17051 — Sonnet 4.6 missed 38 institution abbreviations).
- Professions and odd locations: "firefighter", "Cape Cod" (n2c2 2014,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4989908/).
- Split or long names: "Rayna" + "De Angelis"; a six-token name missed
  half each time (Philter paper).
- Uncommon or regional names, initials, honorific-only references,
  phonetic-alphabet spelling (OpenAI Privacy Filter card).
- Misspelled PHI; structured fields with no context; a patient unique by
  a rare disease (Azure).
- Dates buried in vitals or follow-up lines (arXiv 2608.17051).

## 9. What I downloaded

All under `.../scratchpad/lists/` (full path at the top). Data only; no code run.

| Dir | Files | Lines | License | Sample |
|---|---|---|---|---|
| `philter-ucsf/` | whitelist JSON, first/last name JSON, 133 `safe_regex/*.txt`, LICENSE | 195,253 / 97,014 / 161,470 | BSD-3 | `butorphanol`, `laurel`, `untutored` |
| `physionet-deid/` | `*_ambig.txt`, `medical_phrases.txt`, `notes_common.txt`, `commonest_words.txt` | 7,298 last ambig; 616 + 419 first ambig; 28 phrases | ODC-By 1.0 (page) / GPL-2 (code) | `GEHRIG`, `PARKINSON`, `HOPE` |
| `wikidata-eponyms/disease_eponyms.tsv` | term, named_after | 509 | CC0 | `Brugada syndrome	Josep Brugada; …` |
| `wikipedia-eponyms/eponyms.tsv` | term, source page | 919 | CC BY-SA 4.0 | `Babinski sign`, `Lou Gehrig's disease` |
| `fda-ndc/` | `brand_names.txt`, `substances.txt` | 27,344 / 6,191 | Public domain | `zepbound`, `tirzepatide` |

GPL lists (CRATE, DEDUCE, CliniDeID) are cloned under
`.../scratchpad/repos2/` for reference only.

## Best to reuse

1. **PhysioNet deid ambiguous-name lists + `medical_phrases.txt`**
   (ODC-By 1.0 per PhysioNet page; code is GPL-2, so keep the lists as data,
   don't port the Perl). It's the only list built for exactly our question:
   "this name is also a word, only call it a name with context". 8,300
   ambiguous names, and GEHRIG, PARKINSON, HODGKIN, BABINSKI, WELLS, HOPE,
   MAY, WILL are all in it.
2. **Philter safe regexes + whitelist** (BSD-3). Cleanest license, 195k
   safe words incl. drugs and Hope/Will/Mark/May, and a ready department
   regex. Weak on eponyms: subtract an eponym list before trusting it.
3. **Eponym list built from Wikidata (CC0) + Wikipedia (CC BY-SA), checked
   against CRATE's 535** (GPL; use it to test, not to copy). ~1,000
   surnames. Pair with **FDA NDC + RxNorm prescribable** (public domain)
   for drug brands, especially the name-like ones (Camila, Yasmin, Errin).

For Sage, a list isn't the right shape. A short skill file of categories
with 3–5 examples each (eponyms, name-like drug brands, scores, devices,
departments, place-named diseases) fits in the `name` tag description. Use
the lists to generate test cases and to pre-mask known-safe phrases before
Sage sees the text.

## Gaps nobody covers

- **Clinical scores and scales.** No list anywhere: Wells, Glasgow,
  Gleason, Apgar, Bishop, Ranson, Child-Pugh, MELD, CHA2DS2-VASc, Braden,
  Mallampati, Killip, NIHSS. Write it ourselves (~100 items).
- **Devices and procedures with names**: Foley, Swan-Ganz, Jackson-Pratt,
  Hickman, Port-a-Cath, Whipple, Nissen, Roux-en-Y. Scattered across
  Philter whitelist and Wikipedia procedures; no clean list.
- **Name-like drug brands.** Nobody cross-checks drug lists against
  name lists. Our 164-hit list above is a start.
- **Patient-named eponyms** (Lou Gehrig, Hartnup, Christmas disease):
  most lists are built from physician names and miss these. Wikidata
  missed Lou Gehrig too.
- **Department/service names** beyond Philter's one regex.
- **No "PHI that gets missed" list exists.** Only anecdotes in papers.
  Building one (names that are words: Guy, Bill, Chase, Strong, Hope;
  hospital acronyms; building names; rare-disease uniqueness) would be new.
- **Context rules for LLM checkers.** Every list here is for rule-based
  tools. None is written as guidance for an LLM judge.
