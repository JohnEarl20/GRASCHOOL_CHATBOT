# GABAY.md — Kumpletong Paliwanag ng EarlCHATBOT

**Proyekto:** Cognitive Campus Assistant (EarlCHATBOT)
**Para saan:** Enrollment requirements at student services ng Registrar's Office ng **GRA SCHOOL**
**Curso:** CS ELEC 6
**Developer:** John Earl Mirabete, Tristan Napili

> Ang dokumentong ito ay nakasulat sa **Tagalog** para madaling maintindihan ng buong team.
> Tinuturo nito kung **para saan** ang proyekto, **paano ito gumagana**, **anong wika at library** ang ginamit, at **paano gamitin** ang lahat.

---

## 1. Para saan ang EarlCHATBOT?

Ang **EarlCHATBOT** ay isang chatbot para sa opisina ng Registrar. Ang mga estudyante ay nagtatanong — sa English, Filipino, o Taglish — at sinasagot ng chatbot gamit ang:

- **Confidence score** (gaano katiyak ang sagot, 0% hanggang 100%)
- **Pinagmulan ng sagot** (nanggaling ba ito sa ontology, sa rules, o sa model?)
- **Mga rule na nag-fire** (halimbawa R3, R4, R6)

### Sampol na tanong at sagot

| Tanong ng estudyante | Sagot ng chatbot |

| "What do I need to enroll as a freshman?" | Listahan ng documents: Form 138, PSA Birth Certificate |
| "Can I enroll? Transferee ako, may TOR ako" | "Not yet — kulang pa ang Honorable Dismissal" (rules R3, R4, R6, R7, R13) |
| "When is the payment deadline?" | Petsa ng deadline at kung saan magbabayad |
| "Pakausap po sa staff" | Ipapasa sa tao (hand-off) |

### Bakit mahalaga ito?

Ang mga estudyante ay pumipila sa Registrar para sa simpleng tanong lang — "anong kailangan kong dokumento?" Sinasagot na ng chatbot ito kahit hatinggabi. Ang mga komplikadong kaso ay ipinapasa sa tunay na staff.

---

## 2. Paano Gumagana — Ang Buong Daloy

Kapag may nagtanong, dadaan ang mensahe sa **7 na hakbang**:

Estudyante nag-type ng tanong
        ↓
  [1] NLU — linisin ang teksto, hanapin ang mga salita
        ↓
  [2] Intent Model — ano ang ibig sabihin? (requirements? fees? eligibility?)
        ↓
  [3] Confidence Check — katiyak ba? (≥60%? 40-59%? <40%?)
        ↓
  [4] Rule Engine — kung eligibility, patakbuhin ang 13 rules
        ↓
  [5] Knowledge Base — hanapin ang sagot sa ontology.json
        ↓
  [6] Dialogue — bumuo ng sagot, may memorya ng session
        ↓
  [7] Logger — i-save sa chat_log.jsonl para sa staff dashboard
        ↓
  Sagot na may confidence, pinagmulan, at rules

Isang-isahin natin:

### Hakbang 1 — NLU (Natural Language Understanding)

**File:** `code/nlu.py` (263 linya)

**Ano ang ginagawa:** Binabago ang raw na teksto para maintindihan ng system.

Halimbawa ng input:

"Kumusta po, may TOR ako pero wala akong clearance"

Ang ginagawa ng NLU:

1. **Lowercase** — "kumusta po, may tor ako pero wala akong clearance"
2. **Alisin ang Taglish particles** — "po", "ba", "naman", "kasi", "sana"... (nasusulat sa `PARTICLES` set)
3. **Alisin ang punctuation**
4. **Hanapin ang entities:**
   - `student_type` → ??? (wala sa halimbawang ito)
   - `documents_held` → {tor}
   - `documents_missing` → {clearance}

**Paano nito nalalaman kung MERON o WALA?**

Ginagamit ang state machine na may tatlong mode:

| Salita | Mode | Ibig sabihin |

|---|---|---|
| `have`, `may`, `meron`, `got`, `with` | HAVE | Pagkatapos nito, ang dokumento ay **meron** |
| `no`, `not`, `wala`, `hindi`, `dont`, `wala` | NOT | Pagkatapos nito, ang dokumento ay **wala** |
| `need`, `kailangan` | NEED | Kailangan — **informational lang** |

**Mahalagang detalye:** Ang "dont" at "hindi" ay nasa `NEG_TOKENS` listahan. Kaya ang "i dont have clearance" ay tama — **wala** ang clearance.

**Mahalagang detalye 2:** Kung ang tanong ay interrogative ("do I need a birth certificate?"), **hindi ito nagbabago** ng kung ano ang hawak ng estudyante. Kasi kung magbabago, baka mapunta sa "missing" ang isang dokumentong meron pala siya — dahil lang sa nagtanong siya.

### Hakbang 2 — Intent Model (Machine Learning)

**File:** `code/intent_model.py` (279 linya)

**Ano ang ginagawa:** Sinasabi kung ANONG URI ng tanong ito.

May **10 intents**:

| Intent | Halimbawa ng tanong |

|---|---|
| `greet` | "hi po good morning" |
| `ask_requirements` | "what do I need to enroll as a freshman" |
| `check_eligibility` | "can I enroll, transferee ako may TOR" |
| `ask_schedule_deadline` | "when is the payment deadline" |
| `ask_fees_payment` | "where do I pay the assessment" |
| `ask_office_hours_location` | "what time does the registrar open" |
| `ask_course_prereq` | "prerequisite of CS 201" |
| `ask_clearance_process` | "how do I get my clearance" |
| `request_human` | "pakausap po sa staff" |
| `give_feedback` | "thanks that was helpful" |

**Paano ito natututo?**

1. **TF-IDF Vectorizer** — ginagawang numero ang bawat salita. Kung mas madalas lumabas ang isang salita sa isang uri ng tanong, mas mataas ang "timbang" (weight) nito.
   - Halimbawa: "prerequisite", "CS 201" → mataas ang timbang sa `ask_course_prereq`
   - `ngram_range=(1, 2)` → ginagawang **isahang salita AT dalawang-salitang kombinasyon** (hal. "birth certificate")
2. **Logistic Regression** — pagkatapos maging numero, hinahanap ang pinakamalamang na intent.

**Resulta:** Makakakuha ka ng `(intent, confidence)`, hal. `("ask_requirements", 0.59)`.

**Mahalagang detalye:** Ang 0.59 ay ibig sabihin — 59% confident. Kung ang pangalawang pinakamataas ay 0.09, malinaw na `ask_requirements` ang sagot, kahit 0.59 lang. Kung 0.45 vs 0.42, doon palang nag-aalangan.

### Hakbang 3 — Confidence Check

**File:** `code/dialogue.py` (384 linya)

Tatlong band (mula sa proposal §11):

| Confidence | Ano ang gagawin |

|---|---|
| **≥ 0.60** | Sagutin agad, ipakita ang confidence at pinagmulan |
| **0.40 – 0.59** | Magtanong pabalik (clarify), may buttons |
| **< 0.40** | Fallback message; pagkatapos ng **2 sunod-sunod na palya**, i-hand-off sa staff |

**Isang dokumentadong pagbabago:** Meron kaming `DECISIVE_MARGIN = 0.25`. Ibig sabihin — kung ang pinakamataas na intent ay **mas mataas ng 0.25** kaysa pangalawa, sinasagot namin kahit nasa 0.40–0.59 band.

Bakit? Halimbawa: "What do I need to enroll as a freshman?" → 0.59 (ask_requirements) vs 0.09 (pangalawa). Kung magtatanong pa tayo ng "do you mean requirements or deadlines?", parang tanga — malinaw naman. Kaya sinasagot, at **sinasabi sa card** na may margin.

### Hakbang 4 — Rule Engine (Eligibility)

**File:** `rules_trace.py` (76 linya) + `code/explain.py` (129 linya)

Ito ang **pinaka-matalinong parte** at ito ang **hindi ginagamitan ng ML**. Pure logic ito.

**13 rules (R1–R13):**

| Rule | Kung: | Kaya: |

|---|---|---|
| R1 | `student_type(freshman)` | `needs(form138)` |
| R2 | `student_type(freshman)` | `needs(psa_birth_certificate)` |
| R3 | `student_type(transferee)` | `needs(tor)` |
| R4 | `student_type(transferee)` | `needs(honorable_dismissal)` |
| R5 | `student_type(returning)` | `needs(clearance)` |
| R6 | `needs(?d)` at `not has(?d)` | `missing(?d)` |
| R7 | `missing(?d)` | `docs_incomplete()` |
| R8 | `freshman` + `has(form138)` + `has(psa)` | `docs_complete()` |
| R9 | `transferee` + `has(tor)` + `has(honorable_dismissal)` | `docs_complete()` |
| R10 | `returning` + `has(clearance)` | `docs_complete()` |
| R11 | `docs_complete()` + `fees_paid()` | `eligible(official_enrollment)` |
| R12 | `docs_complete()` + `not fees_paid()` | `next_step(pay_assessment)` |
| R13 | `docs_incomplete()` | `next_step(submit_missing_documents)` |

**Paano ito tumatakbo? (Forward Chaining)**
Ulit-ulit na hinahanap ang mga rule na pwedeng i-fire, hanggang wala nang bago:

Cycle 1: R3 → needs(tor), R4 → needs(honorable_dismissal)
Cycle 2: R6 → missing(honorable_dismissal)
Cycle 3: R7 → docs_incomplete()
Cycle 4: R13 → next_step(submit_missing_documents)

**Tapos na.** Ang sagot ay `next_step(submit_missing_documents)`.

**Paano nito ipinaliwanag ang "bakit"? (Backward Chaining)**
Iba pa ito. Ito ay ang "why this answer?" panel.

Nagsisimula sa **goal**: `eligible(official_enrollment)`.
Tinitingnan kung ano ang kailangan ng R11: `docs_complete()` at `fees_paid()`.
Kung kulang ang `docs_complete()`, hanapin ang rule na gumagawa nito — R9.
Kailangan ng R9: `has(tor)` at `has(honorable_dismissal)`.
Meron siya ng `tor`, pero kulang ng `honorable_dismissal` → **iyan ang blocker**.

Kaya ang sinasabi ng chatbot: *"You still need: Honorable Dismissal."*

### Hakbang 5 — Knowledge Base

**File:** `data/ontology.json` (13.7 KB) + `code/knowledge.py` (284 linya)

**Ano ang ontology?** Isang JSON file na may **11 seksyon**:

| Seksyon | Ano ang nasa loob | Bilang |

|---|---|---|
| `student_types` | freshman, transferee, returning | 3 |
| `requirements` | form138, psa_birth_certificate, tor, honorable_dismissal, clearance | 5 |
| `services` | enrollment, clearance, payment, scholarship, late_enrollment | 5 |
| `offices` | registrar, cashier, guidance, library, osa | 5 |
| `courses` | CS 101, 102, 201, 202, ELEC 6 | 5 |
| `programs` | BSCS, BSIT | 2 |
| `semesters` | 1st at 2nd semester | 2 |
| `deadlines` | enrollment, payment, add/drop, scholarship | 5 |
| `fees` | tuition, misc, lab | 3 |
| `policies` | mga patakaran | 4 |
| `announcements` | mga anunsyo | 2 |

**Bawat record ay may `source` field.** Bakit? Para kung tanungin ka ng panel — "saan galing ang isang ito?" — may sagot ka.

**Mahalaga:** Halos lahat ay naka-mark ng **`DRAFT`**. Ibig sabihin — **placeholder pa lang**. Kailangan pang palitan ng tunay na numero mula sa handbook ng GRA SCHOOL. Sinasabi din ito ng chatbot sa bawat sagot na galing sa DRAFT records.

### Hakbang 6 — Dialogue

**File:** `code/dialogue.py` (384 linya)

**May memorya** ang chatbot bawat session. Natatandaan niya:

- Anong student type ka (`student_type`)
- Anong documents ang meron ka (`documents_held`)
- Anong kulang (`documents_missing`)
- Nagbayad ka na ba (`fees_paid`)

Kaya sa **two-turn conversation**:

Estudyante: "Can I enroll? I am a transferee"
Bot:        [nagtatanong kung anong student type — pero meron na, transferee]

Estudyante: "TOR lang"
Bot:        "Not yet, kulang ang Honorable Dismissal"  ← alam na nya

**Ano ang hand-off?** Pag sinabi ng estudyante na gusto niyang kausapin ang tao, o pagkatapos ng 2 palya — ipapasa sa staff. May note na ibibigay ang Registrar's Office.

### Hakbang 7 — Logger + Analytics

**Files:** `code/logger.py` (48 linya) + `code/forecast.py` (154 linya)

Bawat tanong ay isinasave sa `data/chat_log.jsonl` — isang linya kada tanong.

**Ano ang naka-save?**

- Tanong (text)
- Intent at confidence
- Nasaagot ba?
- Rules na nag-fire
- Feedback (👍 o 👎)

**Ano ang HINDI naka-save?**

- Pangalan
- ID number
- Grades
- Contact details

Sinasabi ito ng chatbot mismo: *"I never ask for your name, ID number, grades or contact details."*

**Para saan ang log?** Para sa **Staff Dashboard**:

- Ilan ang nagtanong?
- Anong topic ang pinakamadalas?
- Anong tanong ang hindi nasasagot?
- **Forecast:** Ilan ang tatanong sa susunod na linggo? (moving average ng huling 3 linggo)
- **Recommendation:** Kailan mag-staff ng mas marami?

---

## 3. Anong Wika at Library ang Ginamit?

### Wika: **Python 3.14**

Bakit Python?

- Madaling basahin ang code
- May napakalakas na libraries para sa ML (`scikit-learn`)
- Maganda para sa NLP at data
- Ang buong team ay marunong

### Mga Library

| Library | Bersyon | Para saan |

|---|---|---|
| **Streamlit** | 1.53.0 | Ang UI — chat at dashboard, walang kailangang HTML/CSS |
| **scikit-learn** | 1.8.0 | Machine learning — TF-IDF, Logistic Regression, Naive Bayes |
| **pandas** | 2.3.3 | Tables at data manipulation (sa dashboard) |
| **numpy** | 2.4.1 | Numero at arrays (ginagamit ng sklearn) |
| **joblib** | 1.5.3 | Pag-save at pag-load ng trained models |
| **openpyxl** | 3.1.5 | Pagbasa ng Excel file (ang starter corpus ay .xlsx na may .csv na pangalan) |

### Paano naka-install?

```bash
python -m pip install -r requirements.txt
```

Lahat ng libraries ay **local** — walang API key, walang internet na kailangan para tumakbo. Ibig sabihin, gumagana ito kahit walang WiFi.

### Bakit Streamlit at hindi React o plain HTML?

1. **Walang JavaScript** — pure Python lang ang isusulat
2. **Mabilis** — ang UI ay nasa `app.py` (543 linya) + `ui/` para sa styling
3. **Automatic** — bawat `st.button()` ay gumagawa ng totoong HTML button
4. **Para sa prototype** — sakto lang para sa demo, hindi kailangang mag-build ng webpack

**Limitasyon ng Streamlit:** sariling DOM ang iginuguhit nito, kaya kayang baguhin ang itsura sa pamamagitan ng CSS, pero **hindi** kayang buoin muli ang layout nang eksaktong katulad ng isang React design. Iyon ang dahilan kung bakit ang dashboard ay kahawig ng reference, hindi kopya nito.

---

## 4. Paano Gamitin — Step by Step

### A. Unang Pag-set Up

```bash
# 1. Pumunta sa project folder
cd c:\EARLCHATBOT

# 2. I-install ang libraries
python -m pip install -r requirements.txt

# 3. I-extract ang starter corpus at pagsamahin
python scripts/prepare_corpus.py

# 4. I-train ang models
python scripts/train_models.py

# 5. Patakbuhin ang app
python -m streamlit run app.py
```

Pagkatapos nito, buksan sa browser:

<http://localhost:8501>

### ⚠️ Mahalagang babala sa Python

**Gamitin ang `python`, HINDI `python3.14.exe`.**

Ang `C:\Users\John Earl Mirabete\.local\bin\python3.14.exe` ay **blocked** ng Application Control policy sa computer na ito. Ang gumagana ay:

C:\Python314\python.exe

Kapag nag-run ka ng `python3.14.exe app.py`, makikita mo:

Program 'python3.14.exe' failed to run: An Application Control policy has blocked this file

Normal `python` lang, gumagana.

### B. Paano Mag-chat

1. Buksan ang `http://localhost:8501`
2. May **apat na views** sa sidebar: **AI Assistant**, **Voice Upload**, **Staff Dashboard**, **Developers**
3. Sa Student chat, i-type ang tanong sa text box sa ibaba
4. Pindutin ang Enter

**Halimbawang tanong:**

- "What do I need to enroll as a freshman?"
- "Can I enroll? I am a transferee and I have my TOR"
- "When is the payment deadline?"
- "Magkano ang tuition?"
- "Kumusta po, may TOR ako pero wala akong clearance"

**May 4 na suggested prompt buttons** sa itaas — pindutin lang para mabilis.

Puwede ring pumasok direkta gamit ang URL:

| View | URL |

|---|---|
| AI Assistant | `?view=chat` |
| Voice Upload | `?view=voice` |
| Staff Dashboard | `?view=dashboard&role=Staff` |
| Developers | `?view=developers` |

### C. Paano Basahin ang Sagot

Ang bawat sagot ay may:

| Bahagi | Halimbawa | Ibig sabihin |

|---|---|---|
| **Confidence badge** | "Confidence 77%" | Gaano katiyak ang model |
| **Rules badge** | "5 rules fired" | Ilang rules ang nagpatakbo |
| **Rules fired** | "R3, R4, R6, R7, R13" | Nasaa "Why this answer?" expander |
| **Buttons** | "Helpful" / "Not helpful" | Feedback mo |
| **Why this answer?** | expander | Paliwanag ng backward chaining |

### D. Sidebar

Sa kaliwa, makikita mo:

1. **Signed in as** — switch ng **Student** / **Staff** (⚠️ demo control lang, hindi login)
2. **Navigation** — apat na views
3. **This session** — natatandaan ba ng bot ang student type at documents mo?
4. **Start over** — i-reset ang session

Kapag **Student**, nakatago ang Staff Dashboard sa navigation. Kapag **Staff**, lumalabas ito.

### E. Voice Upload

1. **Record voice** — pindutin ang start, magsalita, pindutin ang stop. Totoong gumagamit ito ng mikropono ng browser.
2. **Upload an audio file** — drag-and-drop o piliin ang WAV / MP3 / M4A / WEBM
3. **Playback** — mapapakinggan mo ang clip dito mismo.
4. **Walang speech-to-text.** Nag-answer lang ang assistant sa mga naka-type na tanong. I-type sa AI Assistant ang itinanong mo — pareho ang sagot.

### F. Staff Dashboard

Pindutin ang **Staff Dashboard** sa sidebar (o `?view=dashboard&role=Staff`). Dito makikita mo:

1. **KPI cards** — Total questions, Answered %, Unanswered, Next week forecast
2. **Questions per week** — area chart
3. **Top question categories** — horizontal bar chart
4. **Recommendation** — kung kailan mag-staff ng mas marami, may ebidensya at confidence
5. **Unanswered questions** — search box, table, at labeling controls
6. **Feedback** — helpful vs not helpful

**⚠️ Ang data dito ay SAMPLE LANG** — synthetic, galing sa `scripts/seed_sample_logs.py`. Sinasabi ito ng dashboard mismo sa dilaw na babala.

### G. Developers

Dalawang profile card — bilog ang larawan, gradient border, hover animation. Naka-display lang ang totoong naitala sa `data/developer.json` — walang imbentong bio o social links.

Para gumawa ng bagong sample data:

```bash
python scripts/seed_sample_logs.py
```

### F. Paano Mag-test

```bash
python tests/test_app.py
```

Dapat mong makita:

checks passed: 81
ALL CHECKS PASSED

Ano ang tinetest ng 81 checks na ito?

| Kategorya | Bilang | Ano |

|---|---|---|
| Rule cases | 20 | Bawat rule, lahat ng kombinasyon |
| Ontology agreement | 6 | Tugma ba ang ontology sa rules? |
| NLU | 11 | Tama ba ang extraction ng entities? |
| Dialogue | 14 | Clarify, hand-off, memorya |

### G. Paano Mag-retrain

Kung may bago kang data (hal. staff-labelled questions):

```bash
python -m streamlit run app.py
# → Staff dashboard → label → Retrain
```

O sa terminal:

```bash
python scripts/train_models.py
```

---

## 5. Ang Code Structure

| File | Linya | Para saan |

|---|---|---|
| `app.py` | 620 | Streamlit entry point — 4 views sa likod ng sidebar |
| `ui/theme.py` | 495 | Design tokens, glassmorphism CSS, inline Lucide icons |
| `ui/components.py` | 170 | Reusable: brand, nav, KPI, cards, chat bubbles, dev card |
| `rules_trace.py` | 76 | Ang 13 rules at forward chaining (original prototype) |
| `code/nlu.py` | 263 | Text preprocessing, Taglish particles, entity extraction |
| `code/intent_model.py` | 279 | TF-IDF + Logistic Regression intent model |
| `code/sentiment.py` | 136 | Naive Bayes sentiment model |
| `code/knowledge.py` | 284 | Ontology records at answer building |
| `code/explain.py` | 129 | Backward chaining — ano ang blocking |
| `code/dialogue.py` | 384 | Session memory, confidence policy, clarify, hand-off |
| `code/logger.py` | 48 | Chat log para sa dashboard |
| `code/forecast.py` | 154 | Forecast at recommendation |
| `tests/test_app.py` | 299 | 81 tests |
| `scripts/prepare_corpus.py` | 103 | Extract at merge ng corpus |
| `scripts/train_models.py` | 40 | Train models |
| `scripts/seed_sample_logs.py` | 159 | Sample data para sa dashboard |

**Kabuuan:** ~3,400 linya ng Python code.

### Data files

| File | Ano |

|---|---|
| `data/ontology.json` | Knowledge base — 11 seksyon |
| `data/starter_corpus_50.csv` | 50 tanong na sinulat ng team |
| `data/intent_corpus_augmented.csv` | 300 tanong na AI-drafted (para palitan) |
| `data/feedback_corpus.csv` | 120 comments na may label |
| `data/chat_log.jsonl` | Runtime log ng mga tanong |
| `data/developer.json` | Profile ng developers (pangalan, role, larawan) |
| `assets/developer.jpg` | Larawan ni John Earl Mirabete |
| `assets/tristan.jpg` | Larawan ni Tristan Napili |

### Models

| File | Ano |

|---|---|
| `models/intent_model.joblib` | Trained intent model (134 KB) |
| `models/sentiment_model.joblib` | Trained sentiment model (18.5 KB) |
| `models/intent_metrics.json` | Metrics ng intent model |
| `models/sentiment_metrics.json` | Metrics ng sentiment model |

### Assets

| File | Ano |

|---|---|
| `assets/developer.jpg` | Larawan ni John Earl Mirabete |
| `assets/tristan.jpg` | Larawan ni Tristan Napili |

---

## 6. Ang ML Models — Totoong Metrics

Ito ang **totoong numero** mula sa `models/*.json`. Hindi ito hinulaan.

### Intent Model (10 intents)

| Metric | Halaga |
| Corpus size | 326 tanong |
| Intents | 10 |
| Hold-out accuracy | **84.85%** |
| Hold-out macro F1 | **0.848** |
| 5-fold CV macro F1 | **0.8063 ± 0.0616** |
| Target ng proposal | macro F1 ≥ 0.80 |

**⚠️ Mahalagang babala:** Ang hold-out test ay **mula sa parehong distribution** ng training data. Ibig sabihin — **masyadong optimistic**. Hindi pa naipasa ang tunay na target ng proposal (50 tanong na sinulat ng taong hindi nag-sulat ng training phrases), dahil **wala pa** ang set na iyon.

### Sentiment Model

| Metric | Halaga |

| Corpus size | 120 comments |
| Hold-out accuracy | **66.67%** |
| Hold-out macro F1 | **0.644** |
| 5-fold CV macro F1 | **0.5957** |
| Target ng proposal | accuracy ≥ 0.75 |

**⚠️ Hindi pa naabot ang target.** 66.67% vs 75%. Kailangan ng mas maraming comments mula sa iba't ibang tao.

---

## 7. Mga Limitasyon — Ano ang HINDI Pa Gumagana

Maging tapat tayo. Ito ang mga bagay na hindi pa tapos:

| Bagay | Katayuan | Bakit |

|---|---|---|
| **Voice recording** | ✅ Gumagana | Totoong mikropono ng browser + upload ng file |
| **Speech-to-text** | ⛔ Sinadyang alisin | Walang speech recognition — type lang ang tanong |
| **LLM rewording** | ❌ Naka-off | Walang provider na konektado |
| **Login page** | ❌ Sinadya | Walang authentication sa proyekto; ayaw naming gumawa ng pekeng login |
| **Tunay na datos** | ❌ DRAFT pa | Placeholder lang ang mga numero |
| **Log masking** | ❌ Wala pa | Hindi pa nafi-filter ang personal data |
| **Fairness check** | ❌ Wala pa | Kailangan ng 50 unseen questions |
| **Sentiment accuracy** | ⚠️ 66.67% | Mas mababa sa target 75% |

### Ano ang DRAFT?

Lahat ng nasa `data/ontology.json` maliban sa school name ay **placeholder**. Halimbawa:

- "Tuition fee per unit: **PHP 1,500**" ← hindi ito totoo, placeholder lang
- "Registrar hours: **Mon-Fri 8AM-12PM, 1PM-5PM**" ← kailangan pang i-confirm

Kailangan pang palitan ng **tunay** na numero mula sa handbook ng GRA SCHOOL.

---

## 8. Paano Mag-edit ng Karaniwang Bagay

### Palitan ang pangalan ng school

**File:** `data/ontology.json`, linya 3:

```json
"school": "GRA SCHOOL - Registrar's Office"
```

Ito ay **nagbabago automatically** sa greeting. Hindi kailangang i-edit ang code.

### Magdagdag ng developer

**File:** `data/developer.json`:

```json
{
  "developers": [
    { "name": "John Earl Mirabete", "role": "Developer", "photo": "assets/developer.jpg" },
    { "name": "Tristan Napili", "role": "Developer", "photo": "assets/tristan.jpg" }
  ]
}
```

Idagdag mo lang ang pangatlong entry at maglagay ng larawan sa `assets/`.

### Palitan ang deadline

**File:** `data/ontology.json`, kabanata `deadlines`:

```json
{
  "label": "Assessment payment deadline",
  "date": "2026-11-20",
  "confirmed": false
}
```

Gawing `"confirmed": true` pag naconfirm na.

### Magdagdag ng bagong tanong sa training data

**File:** `data/starter_corpus_50.csv` o gumawa ng bago:

```csv
id,text,intent,source,status
S351,guho na ba ang portal,check_eligibility,team-written,reviewed
```

Tapos mag-retrain:

```bash
python scripts/train_models.py
```

### Palitan ang confidence threshold

**File:** `code/dialogue.py`, linya 27-29:

```python
ANSWER_THRESHOLD = 0.60
CLARIFY_THRESHOLD = 0.40
MISSES_BEFORE_HANDOFF = 2
```

**Babala:** Kung babaguhin mo ito, maybe mag-break ang ilang test. Patakbuhin ang `python tests/test_app.py` pagkatapos.

---

## 9. Frequently Asked Questions

### Q: Bakit hindi gumagana ang `python3.14.exe`?

A: Blocked ito ng Application Control policy. Gamitin ang `python` (diretso sa `C:\Python314\python.exe`).

### Q: Kailangan ba ng internet?

A: **Hindi**, para sa base system. Local lahat — models, data, UI. Ang internet ay kailangan lang para sa Google Fonts sa CSS (pwedeng i-off).

### Q: Saan naka-save ang mga tanong ng estudyante?

A: `data/chat_log.jsonl`. Isang linya per tanong. Walang pangalan, walang ID.

### Q: Paano ko made-delete ang logs?

A: Tanggalin ang file:

```bash
rm data/chat_log.jsonl


o mag-generate ng bago:

```bash
python scripts/seed_sample_logs.py
```

### Q: Bakit iba ang "confidence" sa bawat tanong?

A: Depende ito sa:

1. **Gaano kalinaw ang tanong** — "hi" → 85%, "kumusta po" → 70%
2. **Gaano katugma sa training data** — kung bagong phrasing, mas mababa

### Q: Paano ko maipapaliwanag ang "forward chaining" at "backward chaining"?

**Forward chaining** = "ano ang totoo ngayon?"

- Nagsisimula sa facts, paulit-ulit na i-apply ang rules
- Sagot: `next_step(submit_missing_documents)`

**Backward chaining** = "bakit hindi pa ako eligible?"

- Nagsisimula sa goal, bwelta pabalik
- Sagot: "Kulang ka ng Honorable Dismissal"

Parang doctor vs detective:

- **Doctor** (forward): "Kung ganito ang symptoms, ganito ang sakit"
- **Detective** (backward): "Bakit patay? Sino ang pumatay? Paano?"

### Q: Anong pinagkaiba ng ontology at corpus?

- **Ontology** — "anong totoo?" (requirements, deadlines, offices). Sino ang Registrar? Anong oras bukas?
- **Corpus** — "paano magsalita ang estudyante?" (mga tanong). "kailan po mag start ang klase" → `ask_schedule_deadline`

### Q: Bakit Taglish?

A: Ganyan talaga magsalita ang mga estudyante ng GRA SCHOOL. Kung English-only ang chatbot, mahihirapan silang gamitin. Ang NLU ay may listahan ng Taglish particles ("po", "ba", "kasi", "naman") na tinatanggal.

---

## 10. Checklist Bago ang Defense

| ✅ | Bagay |

| ☐ | Patakbuhin ang `python tests/test_app.py` — dapat 81/81 |
| ☐ | Patakbuhin ang app — `python -m streamlit run app.py` |
| ☐ | Palitan ang lahat ng DRAFT sa `data/ontology.json` ng tunay na numero |
| ☐ | I-verify ang office hours, fees, deadlines sa handbook |
| ☐ | Mag-add ng 50 unseen questions (hindi sinulat ng team) |
| ☐ | I-test ang accuracy ng intent model sa unseen questions |
| ☐ | I-test ang accuracy ng sentiment model (**kulang pa sa 75%**) |
| ☐ | I-verify ang English vs Taglish fairness |
| ☐ | Isulat ang log masking para sa personal data |

---

## 11. Quick Reference

### Command cheat sheet

```bash
# Install
python -m pip install -r requirements.txt

# Setup
python scripts/prepare_corpus.py
python scripts/train_models.py

# Run
python -m streamlit run app.py

# Test
python tests/test_app.py

# Sample data
python scripts/seed_sample_logs.py
```

### Constants

| Constant | Value | File | Line |

| `ANSWER_THRESHOLD` | 0.60 | `code/dialogue.py` | 27 |
| `CLARIFY_THRESHOLD` | 0.40 | `code/dialogue.py` | 28 |
| `MISSES_BEFORE_HANDOFF` | 2 | `code/dialogue.py` | 29 |
| `DECISIVE_MARGIN` | 0.25 | `code/dialogue.py` | 38 |

### URLs

| Ano | URL |

| App | `http://localhost:8501` |

---

## 12. Buod

Ang **EarlCHATBOT** ay isang chatbot na:

1. **Nakikinig** sa Tanlish o English — gumagamit ng TF-IDF + Logistic Regression
2. **Naiintindihan** kung anong uri ng tanong — may 10 intents
3. **Sinasagot** gamit ang tunay na data — galing sa ontology.json
4. **Nag-e-explain** ng eligibility — forward + backward chaining sa 13 rules
5. **Nag-aalangan** pag hindi sure — tatlong confidence bands
6. **Nagpapasa sa tao** pag kailangan — hand-off sa staff
7. **Nagtatala** ng lahat — para sa staff dashboard

**Ang pinakamalakas na bahagi:** ang **rules** — sila ang **100% correct** dahil pure logic sila. Tinetest ng 20 hand-made cases.

**Ang pinakamahina:** ang **sentiment model** — 66.67% lang, kulang pa sa target.

**Ang pinaka-incomplete:** ang **DATA** — kailangan pa ng tunay na numero mula sa GRA SCHOOL handbook.

---

*Huling update: 2026-10-22*
*Para sa mga tanong, tumingin sa `README.md` (English) o sa code mismo.*
