"""Seed the chat log with synthetic sample turns so the dashboard can be shown.

    python scripts/seed_sample_logs.py

IMPORTANT: these rows are NOT real students. Every row is marked
"synthetic": true and the dashboard says so, so nobody mistakes the numbers
for what the registrar's office actually received.

The shape of the data is what the proposal expects for a registrar's office:
a weekly cycle with a busy Monday, a mid-week dip, and a spike during the
enrollment period.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code import logger

QUESTIONS = {
    "ask_requirements": [
        "What do I need to enroll as a freshman?",
        "ano po ang requirements para sa transferee",
        "What are the requirements for returning students",
        "Do I need a PSA birth certificate to enroll",
    ],
    "check_eligibility": [
        "Can I enroll? I am a transferee and I have my TOR",
        "pwede na ba ako mag enroll",
        "Am I eligible to enroll this term",
        "check if my documents are complete",
    ],
    "ask_schedule_deadline": [
        "When is the last day of enrollment",
        "Kailan po mag start ang klase",
        "when is the add drop deadline",
        "What is the schedule for late enrollment",
    ],
    "ask_fees_payment": [
        "Where do I pay the assessment",
        "pwede po ba installment ang payment",
        "magkano ang miscellaneous fee",
        "where is the cashier office",
    ],
    "ask_office_hours_location": [
        "What time does the registrar open",
        "saan ang registrar office",
        "is the registrar open on saturday",
        "where is the library located",
    ],
    "ask_course_prereq": [
        "What is the prerequisite of CS 201",
        "anong prerequisite ng cs elec 6",
        "how many units can I take this semester",
        "Can I take Data Structures without Programming 1",
    ],
    "ask_clearance_process": [
        "How do I get my clearance",
        "ano po ang process ng clearance",
        "who signs the clearance form",
        "do I need clearance before enrolling again",
    ],
    "request_human": [
        "I want to talk to a staff member",
        "Pakausap po sa registrar staff",
        "can you connect me to a real person",
    ],
    "give_feedback": [
        "Thanks that was helpful",
        "the answer was wrong I wasted my time",
        "ang bilis ng sagot salamat po",
    ],
    "greet": ["hi po good morning", "hello", "kumusta po"],
}

# Questions the assistant could not answer - the review list for staff.
UNANSWERED = [
    "Where do I get the scholarship form",
    "Do you accept the new portal for the assessment",
    "Is the office open during the foundation day",
    "Can I pay using GCash on the weekend",
    "What is the effectivity date of the form 138",
]

# Monday is the busiest day for a registrar's office, Friday is next, and the
# weekend is quiet. Monday to Sunday.
DAY_WEIGHTS = [0.26, 0.13, 0.12, 0.13, 0.17, 0.11, 0.08]


def main() -> None:
    random.seed(42)
    start = datetime.now() - timedelta(weeks=8)
    rows = []

    for week in range(8):
        week_start = start + timedelta(weeks=week)
        # Anchor every week on its Monday, so the weights below really do
        # describe Monday to Sunday.
        week_start = week_start - timedelta(days=week_start.weekday())
        # Volume grows towards the enrollment period.
        base = 26 + week * 4
        for day_offset, weight in enumerate(DAY_WEIGHTS):
            day = week_start + timedelta(days=day_offset)
            count = max(0, int(base * weight + random.uniform(-2, 2)))
            for _ in range(count):
                when = day.replace(
                    hour=random.randint(8, 16),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                )
                if random.random() < 0.06:
                    intent = "unknown"
                    text = random.choice(UNANSWERED)
                    answered = False
                    confidence = round(random.uniform(0.08, 0.38), 2)
                else:
                    intent = random.choices(
                        list(QUESTIONS.keys()),
                        weights=[16, 22, 14, 13, 11, 9, 8, 6, 6, 5],
                    )[0]
                    text = random.choice(QUESTIONS[intent])
                    answered = True
                    confidence = round(random.uniform(0.61, 0.97), 2)
                rows.append(
                    {
                        "ts": when.isoformat(timespec="seconds"),
                        "session_id": f"seed{week}{day_offset}",
                        "text": text,
                        "intent": intent,
                        "confidence": confidence,
                        "answered": answered,
                        "clarified": False,
                        "source": "synthetic - sample data",
                        "rules_fired": [],
                        "facts": [],
                        "escalated": False,
                        "sentiment": None,
                        "student_type": None,
                        "synthetic": True,
                    }
                )

    with logger.LOG_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} synthetic turns to {logger.LOG_PATH}")
    print("These are sample rows for the dashboard demo - they are not real students.")


if __name__ == "__main__":
    main()
