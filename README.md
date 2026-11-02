# GRA SCHOOL — Cognitive Campus Assistant

An explainable enrollment requirements and student services advisor built for the Registrar's Office of **GRA SCHOOL**. Students and staff interact with the assistant in English, Filipino, or Taglish. The system delivers transparent answers complete with confidence scores, source citations from the school ontology, and the exact rules that fired.

Built for **CS ELEC 6 (Introduction to Cognitive Computing)** by **John Earl Mirabete** and **Tristan Napili**.

---

## Quick Start

### 1. Installation & Preparation

```bash
# Install dependencies
python -m pip install -r requirements.txt

# Extract and merge the training corpus
python scripts/prepare_corpus.py

# Train intent classification and sentiment models
python scripts/train_models.py
```

### 2. Run the Application

```bash
# Launch Streamlit on local port 8501
python -m streamlit run app.py
```

Open your browser to: **http://localhost:8501**

### 3. Run Regression Checks & Tests

```bash
python tests/test_app.py

> All **81 verification checks** must pass cleanly across the 13 rule cases, ontology schema consistency, Taglish NLU extraction, and conversation state management.

*(Note: On Windows, use `python`, not `python3.14.exe` if local path restrictions apply. The standard interpreter is `C:\Python314\python.exe`.)*

---

## Authentication & Role-Based Access Control

The application implements a unified authentication system (`code/auth.py`) with salted PBKDF2-SHA256 password hashes and role separation. Existing SHA-256 student credentials remain valid and are verified during login. Account data is stored locally in `data/users.json` and is not included in the repository:

- **🎓 Student Accounts**:
  - Access to the **AI Assistant** conversation interface.
  - Access to the **Voice Upload** audio recording tool.
  - Access to a focused **Settings** view with personalized AI confidence preferences, security/password controls, notification settings, and system monitoring.

- **👨‍🏫 Staff Accounts**:
  - Access to the staff-only workspace: dashboard, inquiry/support conversations, question review, verified knowledge articles, documents, announcements, analytics, and staff settings.
  - Public registration creates student accounts only. Staff self-registration and staff account creation by ordinary staff accounts are disabled.
  - Authorized administrators can create staff accounts through **Staff Management**. The account is saved to the existing `data/users.json` store with a unique Staff ID and Official Email, and the staff member can log in immediately.

### Configure Staff Administrators

Staff Management is restricted to staff IDs explicitly allowlisted by the deployment owner. Add one or more existing staff IDs to `STAFF_ADMIN_IDS` in the server environment or `.env` file, separated by commas:

```dotenv
STAFF_ADMIN_IDS=registrar-admin-01,school-admin-02
```

For Streamlit Community Cloud, configure the IDs in app secrets:

```toml
STAFF_ADMIN_IDS = ["registrar-admin-01", "school-admin-02"]
```

The allowlisted IDs must already belong to staff accounts. Do not configure student IDs or grant the setting to every staff account.

Students can register through the **Create Account** sidebar view. Staff accounts are provisioned only from the admin-only **Staff Management** page.

If a deployment has no `data/users.json` yet, the deployment owner can create its first administrator through private environment variables or Streamlit secrets:

```toml
BOOTSTRAP_ADMIN_ID = "registrar-admin-01"
BOOTSTRAP_ADMIN_PASSWORD = "use-a-unique-secret-password"
BOOTSTRAP_ADMIN_NAME = "Registrar Administrator"
BOOTSTRAP_ADMIN_EMAIL = "registrar-admin@gra.edu"
BOOTSTRAP_ADMIN_DEPARTMENT = "Registrar"
```

Both `BOOTSTRAP_ADMIN_ID` and `BOOTSTRAP_ADMIN_PASSWORD` are required for bootstrap. On first account-store access, the application hashes the password and creates a staff administrator in `data/users.json`; that ID is authorized to use Staff Management. Remove the bootstrap credentials after the deployment has durable account storage and verify an administrator can log in first. Login IDs are matched case-insensitively, while the original saved ID is retained.

The current account database is a local JSON file. On hosting platforms with ephemeral filesystems, the bootstrap account can be recreated from secrets after a restart, but separately created accounts may not persist. Configure a durable database before relying on long-lived account records.

---

## Core Capabilities & Architecture

User Query (English / Filipino / Taglish)
                     ↓
  [1] NLU Layer (`code/nlu.py`)
      • Lowercasing, particle normalization ("po", "ba", "kasi", "naman")
      • Entity extraction (student_type, documents_held, documents_missing)
                     ↓
  [2] Learning Layer (`code/intent_model.py`)
      • Scikit-learn TF-IDF Vectorizer + Logistic Regression (10 Intents)
      • Naive Bayes Sentiment Classifier for student feedback
                     ↓
  [3] Policy & Dialogue Layer (`code/dialogue.py`)
      • Banded confidence thresholds (Answer ≥ 0.60, Clarify 0.40–0.59, Fallback < 0.40)
      • Margin-of-victory heuristic (answers if top intent beats runner-up by ≥ 0.25)
      • Session memory for accumulated student facts and documents
                     ↓
  [4] Cognitive Reasoning Layer (`code/explain.py` & `rules_trace.py`)
      • Forward chaining over 13 registrar handbook rules
      • Backward chaining explanation ("Why this answer?") identifying blocking facts
                     ↓
  [5] Knowledge Base (`code/knowledge.py` & `data/ontology.json`)
      • 11 ontology sections: Requirements, Deadlines, Fees, Offices, Services, etc.
                     ↓
  [6] Presentation Layer (`ui/`)
      • Streamlit wide-layout responsive web app
      • Full-page GRA SCHOOL campus background wallpaper (`static/campus-bg.png`)
      • Cyber-blue futuristic glassmorphism design system (`ui/theme.py`)
      • Reusable presentation widgets and profile cards (`ui/components.py`)
      • Advanced 10-module settings dashboard (`ui/settings_dashboard.py`)

---

## What the Assistant Knows (10 Intents)

| Intent | Source | Example Query |

|---|---|---|

| `greet` | Conversation state | *"Hi po, good morning!"* |
| `ask_requirements` | Ontology — `Requirement` | *"What do I need to enroll as a freshman?"* |
| `check_eligibility` | Rule Base — Forward Chaining | *"Can I enroll? Transferee ako and I have my TOR."* |
| `ask_schedule_deadline` | Ontology — `Deadline` | *"When is the assessment payment deadline?"* |
| `ask_fees_payment` | Ontology — `Fee` | *"How much is the tuition fee and where do I pay?"* |
| `ask_office_hours_location` | Ontology — `Office` | *"What time does the registrar open?"* |
| `ask_course_prereq` | Ontology — `Course` | *"What is the prerequisite for CS 201?"* |
| `ask_clearance_process` | Ontology — `Service` | *"Paano kumuha ng clearance para sa transferee?"* |
| `request_human` | Staff Hand-Off | *"Pakausap po sa human registrar staff."* |
| `give_feedback` | Sentiment Model | *"Salamat po, very helpful ang sagot!"* |

---

## The Four Application Views

1. **AI Assistant (`/?view=chat`)**:
   - Conversational chat interface featuring student and assistant bubbles.
   - Expandable answer metadata cards showing exact confidence percentages, source documents, rules fired, and backward-chaining explanations.
   - Quick suggested prompt buttons for common enrollment inquiries.
   - Dynamic sidebar profile card displaying user role, name, and live online indicator.

2. **Voice Upload (`/?view=voice`)**:
   - In-browser microphone audio recording (`st.audio_input`).
   - Drag-and-drop audio file upload supporting WAV, MP3, M4A, and WEBM.
   - Native audio playback preview. *(Note: Voice input is record-and-play only; queries are answered by typing into the AI Assistant view).*

3. **Staff Analytics Dashboard (`/?view=dashboard`)**:
   - Restricted to authenticated staff accounts.
   - Four high-level KPIs: Total logged turns, Answer rate, Escalation rate, and Positive feedback ratio.
   - Altair SVG charts: Weekly question volume trend, queries by category bar chart, and sentiment distribution.
   - Time-series volume forecasting for peak enrollment periods.
   - Unanswered queries triage table with manual staff review tools.

4. **Staff Workspace (`/?view=dashboard`)**:
   - Dark glassmorphism dashboard using the existing GRA campus and mascot artwork.
   - Analytics & Reports provides period, date, category, status, and staff filters with inquiry trends, category and status charts, weekday activity, KPI comparisons, searchable inquiry records, and activity-based recommendations.
   - Staff can generate and preview inquiry, AI performance, unanswered, category, staff activity, semester, and operations reports, then download CSV, Excel, or PDF and print the page.
   - Generated report files and the last 100 report-history entries are stored locally under `data/staff_reports/`, excluded from Git, and report creation is audit-logged.
   - Question review can add staff labels to the existing training corpus.
   - Staff-approved knowledge articles are stored locally and are the only newly authored articles used by the assistant.
   - Staff documents and announcements use local file/JSON storage; published announcements appear in the student assistant.
   - Verified accuracy and response-time metrics are reported only when corresponding evaluation/timing records exist. No analytics API or relational database is configured; the dashboard uses existing local log and conversation files.

5. **Advanced Futuristic Settings Dashboard (`/?view=settings`)**:
   - Re-designed to match the GRA SCHOOL futuristic educational dashboard design reference.
   - **For Staff**: 10 comprehensive management categories:
     1. *Overview* — Interactive 2-column quick configuration grid.
     2. *General* — Language, time zone, and date format preferences.
     3. *AI Assistant* — Personality, response length, language, and confidence threshold sliders.
     4. *Security* — Live password change, 2FA toggle, session inactivity timeout, and brute-force protection.
     5. *Users* — Account table and administrative user provisioning.
     6. *Notifications* — System notices, announcements, document reminders, and sound alerts.
     7. *Database* — Storage health inspector, automatic backup scheduling, manual ZIP archive creation, and JSONL log export.
     8. *System* — Live hardware telemetry using `psutil` (CPU load, RAM utilization, continuous uptime).
     9. *School* — Institutional metadata editor syncing directly with `data/ontology.json`.
     10. *Logs* — System activity and audit trail with clear history function.
     - Right-side System Status panel, Quick Action buttons, and Recent Changes audit feed.
   - **For Students / Users**:
     - Clean, focused interface containing only relevant categories: *Overview*, *AI Assistant Configuration*, *Security & Password*, *Notifications*, and *System Monitoring*.
     - Preferences persist to `data/app_prefs.json` and automatically reload across sessions.

6. **Developers Page (`/?view=developers`)**:
   - Profile cards for project developers (John Earl Mirabete and Tristan Napili).
   - Embedded within the Settings workspace for clean navigation.

---

## Directory Structure

```text
├── app.py                      # Main Streamlit application and view router
├── rules_trace.py              # Forward chaining rule engine & 13 registrar rules
├── requirements.txt            # Pinned Python package dependencies
├── README.md                   # Complete system documentation
├── GABAY.md                    # Detailed Filipino/Taglish reference guide
├── CSELEC6_TeamName_...docx    # Prefinal-final project proposal document
├── ui/
│   ├── theme.py                # Design tokens, cyber-blue CSS, Lucide icons
│   ├── components.py           # Presentation components, user card, banners
│   └── settings_dashboard.py   # Advanced futuristic settings dashboard
├── code/
│   ├── auth.py                 # Unified authentication & SHA-256 password hashing
│   ├── dialogue.py             # Session state, threshold policy, hand-off
│   ├── nlu.py                  # Taglish particle normalization & entity extraction
│   ├── intent_model.py         # TF-IDF + Logistic Regression intent classifier
│   ├── sentiment.py            # Naive Bayes student feedback classifier
│   ├── knowledge.py            # Ontology query handler and record retrieval
│   ├── explain.py              # Backward chaining rule-block explainability
│   ├── logger.py               # JSONL turn logging for analytics
│   ├── forecast.py             # Altair charts and weekly inquiry volume forecast
│   ├── analytics_reports.py    # Staff report exports, PDF creation, and report history
│   └── staff_gate.py           # Legacy registrar passcode gate support
├── data/
│   ├── users.json              # Hashed credentials and user accounts
│   ├── app_prefs.json          # Persistent assistant & system configuration
│   ├── ontology.json           # 11 registrar knowledge classes and facts
│   ├── starter_corpus_50.csv   # Human-written baseline labeled queries
│   ├── intent_corpus_augmented.csv # Augmented training inquiries
│   ├── feedback_corpus.csv     # Labeled sentiment feedback data
│   ├── chat_log.jsonl          # Session turn logs for staff analytics
│   └── backups/                # Zipped database and configuration archives
├── models/
│   ├── intent_model.joblib     # Pickled scikit-learn intent pipeline
│   ├── sentiment_model.joblib  # Pickled scikit-learn sentiment pipeline
│   └── intent_metrics.json     # Hold-out evaluation metrics
├── static/
│   └── campus-bg.png           # High-resolution campus wallpaper asset
├── scripts/
│   ├── prepare_corpus.py       # Corpus ingestion and preprocessing
│   ├── train_models.py         # Scikit-learn model training script
│   └── seed_sample_logs.py     # Generates synthetic data for dashboard testing
└── tests/
    └── test_app.py             # 81 regression and verification checks
```

---

## Technical Defense & Evaluation Q&A

### Q1: Bakit hybrid approach (Machine Learning + Rule-Based)?

**Sagot:**
Hindi mapagkakatiwalaan ang purong Machine Learning o generative LLM sa mga kritikal na patakaran ng eskwelahan tulad ng enrollment eligibility dahil may posibilidad ng hallucination. Sa kabilang banda, hindi naman kayang intindihin ng purong rule-based system ang samu't saring paraan ng pagtatanong ng mga estudyante (Taglish, slang, typos).

Kaya gumamit ang sistema ng **Hybrid Architecture**:

1. **Machine Learning (TF-IDF + Logistic Regression)** ang sumasala sa natural language at nagtutukoy ng `intent`.
2. **Rule-Based Forward Chaining Engine** (13 handbook rules) ang gumagawa ng 100% deterministikong desisyon kung kwalipikado nang mag-enroll ang estudyante.
3. **Ontology Knowledge Base** ang nagbibigay ng opisyal na impormasyon sa requirements, deadlines, at fees.

### Q2: Paano gumagana ang "Why this answer?" (Explainability)?

**Sagot:**
Gumagamit ang system ng **Backward Chaining** (`code/explain.py`). Kapag nagtanong ang estudyante ng *"Can I enroll?"*, sinusuri ng engine ang goal state na `eligible(official_enrollment)`. Kung hindi pa ito naabot, sinusuri pabalik ang dependency tree ng mga patakaran para matukoy kung aling partikular na dokumento (hal. `tor`, `honorable_dismissal`, o `clearance`) ang kulang. Ipinapakita ito sa estudyante bilang malinaw na listahan ng mga dokumentong mayroon na sila, mga kulang pa, at ang mga partikular na rule IDs na nag-fire.

### Q3: Paano pinapangalagaan ang data privacy ng mga estudyante?

**Sagot:**
Alinsunod sa **Data Privacy Act of 2012 (RA 10173)**:

- Hindi kailanman humihingi ang assistant ng sensitibong impormasyon tulad ng
grado, buong address, o financial bank details habang nakikipag-usap.
- Ang mga dokumentong binabanggit ng estudyante sa chat ay pansamantalang nakatago lamang sa **in-memory session state** at awtomatikong nawawala kapag nag-reset ang session.
- Ang mga password sa `data/users.json` ay naka-encrypt gamit ang **SHA-256 cryptographic hashing**.
- Ang mga chat logs na iniimbak para sa staff analytics ay limitado sa query text, classified intent, confidence score, at rules fired nang walang personal identity linkage.

---

## Project Status & Verification

- **Current Build**: `v2.0.0`
- **Unit & Integration Tests**: `python tests/test_app.py` passed (**81 / 81 checks**).
- **Intent Classifier**: Hold-out accuracy `0.86`, Macro F1 `0.86` across 10 intents.
- **Design System**: Fully responsive dark-glass UI with full-page campus wallpaper, live hardware telemetry, and role-tailored dashboard controls.
