# Cognitive Campus Assistant

An enrollment requirements and student services advisor for the Registrar's
Office. Students ask in English, Filipino or Taglish; the assistant answers
with a confidence score, the source of the answer, and the rules that fired.

Built to the architecture in `CSELEC6_TeamName_Prefinal_Proposal.pdf`
(sections 5 to 13): the rule base answers the fixed policy, the trained model
handles the language, and the staff dashboard shows what the office should
look at next.

---

## Run it

```bash
python -m pip install -r requirements.txt
python scripts/prepare_corpus.py     # extract the starter corpus, merge the rest
python scripts/train_models.py       # train the intent and sentiment models
python -m streamlit run app.py       # open http://localhost:8501
```

Optional, for the staff dashboard demo:

```bash
python scripts/seed_sample_logs.py   # 292 synthetic turns, clearly flagged as synthetic
```

Run the tests:

```bash
python tests/test_app.py             # 81 checks
```

Use `python`, not `python3.14.exe` - the copy in
`C:\Users\John Earl Mirabete\.local\bin\` is blocked by an Application Control
policy on this machine. The working interpreter is `C:\Python314\python.exe`.

---

## What the assistant does

| Intent | Answered from | Example |
    |---|---|---|
| `greet` | conversation + privacy notice | "hi po good morning" |
| `ask_requirements` | ontology - Requirement | "what do I need to enroll as a freshman" |
| `check_eligibility` | rule base - forward chaining | "can I enroll, transferee ako may TOR" |
| `ask_schedule_deadline` | ontology - Deadline | "when is the payment deadline" |
| `ask_fees_payment` | ontology - Fee | "where do I pay the assessment" |
| `ask_office_hours_location` | ontology - Office | "what time does the registrar open" |
| `ask_course_prereq` | ontology - Course | "prerequisite of CS 201" |
| `ask_clearance_process` | ontology - Service | "how do I get my clearance" |
| `request_human` | hand-off | "pakausap po sa staff" |
| `give_feedback` | sentiment model | "thanks that was helpful" |

The eligibility answer is never written by hand - it is the conclusion of the
13 rules in `rules_trace.py`, and the answer shows the rules that fired. The
"why this answer" panel is backward chaining: it walks back from
`eligible(official_enrollment)` to the fact that is missing.

---

## Layout

```text
app.py                    Streamlit entry point: 4 views behind a sidebar
rules_trace.py            the 13 rules and the forward chaining engine (original prototype)
ui/
  theme.py                design tokens, glassmorphism CSS, inline Lucide icons
  components.py           reusable pieces: brand, nav, KPI, cards, chat bubbles
code/
  nlu.py                  preprocessing, Taglish particle removal, entity extraction
  intent_model.py         TF-IDF + logistic regression intent model
  sentiment.py            Naive Bayes feedback sentiment model
  knowledge.py            the ontology records and the answers built from them
  explain.py              backward chaining - what is blocking this student
  dialogue.py             session memory, confidence policy, clarification, hand-off
  logger.py               the chat log the dashboard reads
  forecast.py             weekly volume forecast and the staff recommendation
data/
  ontology.json           11 sections, every record with a source note
  starter_corpus_50.csv   the team's own 50 labelled questions
  intent_corpus_augmented.csv  300 AI-drafted questions to extend it
  feedback_corpus.csv     120 comments labelled positive / neutral / negative
  chat_log.jsonl          runtime log (one JSON line per turn)
  developer.json          the developer profiles shown on the Developers page
models/                   trained artifacts + the metrics shown in the dashboard
assets/                   developer portraits
scripts/                  prepare_corpus.py, train_models.py, seed_sample_logs.py
tests/test_app.py         81 checks
```

### The four views

| View | URL | What it shows |
|---|---|---|
| AI Assistant | `/?view=chat` | The conversation, suggested prompts, answer cards |
| Voice Upload | `/?view=voice` | Browser recording + audio upload with playback |
| Staff Dashboard | `/?view=dashboard&role=Staff` | KPIs, charts, recommendation, unanswered table |
| Developers | `/?view=developers` | Profile cards with circular portraits |

Views are addressable by query parameter, so any page can be bookmarked or
linked directly. `?role=Student` hides the dashboard nav entry; `?role=Staff`
shows it. The role switch is a demo control, **not authentication** - this
project has no login, so no password is asked for or checked.

### Design system

Dark navy canvas with royal-blue and violet gradients, glassmorphism panels,
Inter throughout, and inline Lucide SVG icons (no emoji, no icon font).
Charts are built with Altair rather than `st.line_chart`, because Streamlit's
built-in charts render to canvas and cannot be recoloured by CSS - they stayed
a white box on the dark canvas. Altair renders to SVG and takes the palette.

---

## The confidence policy

Proposal section 11 sets three bands. They are implemented in
`code/dialogue.py`:

| Confidence | Behaviour |
|---|---|
| >= 0.60 | answer, with the confidence, the source and the rules that fired |
| 0.40 - 0.59 | clarify, with buttons |
| < 0.40 | fallback message; after two misses, hand off to a staff member |

**One documented deviation.** With a 324-question corpus the model is often
right but not confident: "What do I need to enroll as a freshman?" scored 0.59
for `ask_requirements` against 0.09 for the runner-up. Answering the
proposal's literal policy there means asking "do you mean requirements or
deadlines?" about an unambiguous question. So a top intent that beats the
runner-up by 0.25 or more is answered even inside the clarify band, and the
answer card says so and shows the real confidence. Genuinely ambiguous
questions still get the clarifying question.

---

## What the numbers are

Measured on this machine with `python scripts/train_models.py`:

| Model | Hold-out | Cross-validation | Proposal target |
      |---|---|---|---|
| Intent (324 questions, 10 intents) | accuracy 0.86, macro F1 0.86 | 5-fold macro F1 0.81 +/- 0.08 | macro F1 >= 0.80 on 50 unseen questions |
| Sentiment (120 comments) | accuracy 0.67, macro F1 0.64 | 5-fold macro F1 0.60 | >= 0.75 accuracy, per-class F1 |

Read these carefully before they go in the proposal:

- **The intent hold-out is optimistic.** It is drawn from the same writer
  distribution as the training data. The proposal's target - macro F1 on 50
  questions written by a member who did not write the training phrases - cannot
  be claimed until that set exists. The proposal's Figure 5 mockup already
  says "illustrative sample data", and the model metrics file repeats this.
- **The sentiment model misses the 0.75 target.** 0.67 accuracy on the hold-out
  is below the target in proposal section 13. More comments, written by
  different people, are the fix; the model itself is only the baseline.
- **The corpus is partly AI-drafted.** `data/starter_corpus_50.csv` is the
  team's own writing. The 300 added questions are AI drafts, marked
  `source = AI-drafted draft (no real people)` and
  `status = to be replaced by Member B`. 26 of them were exact repeats of the
  team's wording after normalization and were dropped, so 324 rows are used.
  Member B still has to replace the drafts before the data card is honest.
- **The rules are the solid part.** 20 hand-made rule cases, the agreement
  between the ontology and the rule base, the entity extraction and the
  conversation behaviour are covered by 81 checks that pass.

---

## Known gaps

These are deliberately not finished, and the interface says so instead of
pretending:

- **Voice is record-and-play only.** The browser microphone (`st.audio_input`)
  and drag-and-drop upload for WAV/MP3/M4A/WEBM both work, and the clip plays
  back. There is **no speech-to-text**: the assistant answers typed questions,
  so type what you asked on the AI Assistant page. Speech recognition was
  deliberately left out rather than half-built.
- **The optional LLM reword step is off and unwired.** The toggle exists and
  is off by default (proposal section 5). No provider is connected, so every
  answer is still the one the rules and the knowledge base produced. The
  "turn off the LLM" test therefore passes trivially - decide as a team
  whether to add a provider.
- **Every value in `data/ontology.json` is a draft.** The amounts, dates and
  office hours were written by the team as placeholders and are marked
  `DRAFT` in each record's source note. The answers carry that warning. They
  have to be replaced with values taken from the actual handbook and posted
  announcements before anyone acts on them.
- **The chat log is not yet filtered for personal data.** The assistant never
  asks for a name or an ID number, but a student can still type one into a
  question. Proposal section 14 says the logs are masked; that masking step is
  not written yet.
- **The proposal points at `code/rules_trace.py`; the engine is at the project
  root.** Move it into `code/` or correct the proposal before the defense.
- **No fairness check yet.** Proposal section 13 asks for the accuracy gap
  between English and Taglish groups, and between clear and noisy audio. The
  per-class recall is in `models/intent_metrics.json`; the group split needs
  the 50 unseen questions.

---

## Privacy

The assistant never asks for a name, ID number, grades or contact details, and
the first screen says so. The log stores the question, the intent, the
confidence, whether it was answered and the rules that fired - no identity
fields. The `has` facts used by the rule base are the documents the student
said they hold, and they live in the session only.
