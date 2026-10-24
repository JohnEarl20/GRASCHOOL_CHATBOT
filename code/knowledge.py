"""Knowledge layer: the ontology records and the answers built from them.

Proposal section 8 stores the knowledge base as a JSON ontology with 12
classes; section 11 names which class answers which intent. Every answer
carries the record it came from, and every record carries its own source note
- the team has to be able to say where an answer came from at the defense.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = ROOT / "data" / "ontology.json"

DOCUMENT_LABELS = {
    "form138": "Form 138 (School Record)",
    "psa_birth_certificate": "PSA Birth Certificate",
    "tor": "TOR (Transcript of Records)",
    "honorable_dismissal": "Honorable Dismissal",
    "clearance": "Clearance",
}

# Every fact the rule base can talk about, in plain language. Used when the
# backward chaining explains what is blocking the student.
FACT_LABELS = {
    **DOCUMENT_LABELS,
    "fees_paid": "the assessment payment",
}

INTENT_SOURCE = {
    "ask_requirements": "ontology - Requirement",
    "ask_schedule_deadline": "ontology - Deadline",
    "ask_fees_payment": "ontology - Fee",
    "ask_office_hours_location": "ontology - Office",
    "ask_course_prereq": "ontology - Course",
    "ask_clearance_process": "ontology - Service",
    "check_eligibility": "rules - forward chaining",
}


@dataclass
class KnowledgeAnswer:
    text: str
    source: str
    records: list[dict] = field(default_factory=list)
    draft: bool = False


_ONTOLOGY: dict | None = None


def load() -> dict:
    global _ONTOLOGY
    if _ONTOLOGY is None:
        _ONTOLOGY = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return _ONTOLOGY


def _is_draft(record: dict) -> bool:
    return "DRAFT" in (record.get("source", "") + record.get("status", "")).upper()


def _draft_banner() -> str:
    return (
        "_These records are still team drafts. Confirm the dates and amounts with "
        "the Registrar's Office before you act on them._"
    )


def _requirements_for(student_type: str | None) -> list[dict]:
    requirements = load()["requirements"]
    if student_type:
        return [r for r in requirements if student_type in r["applies_to"]]
    return requirements


def required_documents(student_type: str | None) -> list[str]:
    """Requirement ids for one student type - the same list R1-R5 derive.

    The ontology and the rule base have to agree, so this is checked in
    tests/test_rules_agreement.py.
    """
    if not student_type:
        return []
    return [r["id"] for r in load()["requirements"] if student_type in r["applies_to"]]


def answer_requirements(student_type: str | None) -> KnowledgeAnswer:
    requirements = _requirements_for(student_type)
    if not requirements:
        return KnowledgeAnswer(
            "I do not have a requirement list for that student type yet.",
            source="ontology - Requirement",
        )
    heading = (
        f"Documents for a {student_type} student:"
        if student_type
        else "Documents by student type:"
    )
    lines = [f"**{heading}**", ""]
    for req in requirements:
        scope = ", ".join(req["applies_to"])
        lines.append(f"- **{req['name']}** - issued by {req['issuing_body']} ({scope})")
        lines.append(f"  - {req['description']}")
    lines.append("")
    lines.append(f"Where: {load()['offices'][0]['name']} - {load()['offices'][0]['location']}.")
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - Requirement",
        records=requirements,
        draft=any(_is_draft(r) for r in requirements),
    )


def answer_schedule(keyword: str | None = None) -> KnowledgeAnswer:
    deadlines = load()["deadlines"]
    if keyword:
        picked = [d for d in deadlines if keyword in d["label"].lower()]
        if picked:
            deadlines = picked
    lines = ["**Enrollment dates for this term**", ""]
    for item in deadlines:
        mark = "" if item.get("confirmed") else " _(not confirmed yet)_"
        lines.append(f"- {item['label']}: {item['date']}{mark}")
    lines.append("")
    lines.append("Enrollment is done at the Registrar's Office, Main Building Room 101.")
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - Deadline",
        records=deadlines,
        draft=any(not d.get("confirmed", False) for d in deadlines),
    )


def answer_fees() -> KnowledgeAnswer:
    fees = load()["fees"]
    lines = ["**Assessment fees (draft amounts - confirm with the Cashier)**", ""]
    for fee in fees:
        lines.append(f"- {fee['label']}: PHP {fee['amount']:,}")
    options = fees[0]["payment_options"]
    lines += ["", "**Payment options**"]
    lines += [f"- {option}" for option in options]
    cashier = next(o for o in load()["offices"] if o["id"] == "cashier")
    lines += [
        "",
        f"**Where to pay:** {cashier['name']} - {cashier['location']}, {cashier['hours']}.",
        "An official receipt is required - the Registrar will ask for it.",
    ]
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - Fee",
        records=fees,
        draft=any(not f.get("confirmed", False) for f in fees),
    )


def answer_office(office_id: str | None = None) -> KnowledgeAnswer:
    offices = load()["offices"]
    if office_id:
        offices = [o for o in offices if o["id"] == office_id] or offices
    lines = ["**Offices you can go to**", ""]
    for office in offices:
        lines.append(f"- **{office['name']}** - {office['location']}")
        lines.append(f"  - Hours: {office['hours']}")
        lines.append(f"  - Handles: {', '.join(office['handles'])}")
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - Office",
        records=offices,
        draft=any(_is_draft(o) for o in offices),
    )


def answer_course(course_code: str | None = None) -> KnowledgeAnswer:
    courses = load()["courses"]
    programs = {p["code"]: p for p in load()["programs"]}
    if course_code:
        wanted = course_code.upper().replace("  ", " ")
        picked = [c for c in courses if c["code"] == wanted]
        if not picked:
            # Tolerate "cs201" written without a space.
            squashed = wanted.replace(" ", "")
            picked = [c for c in courses if c["code"].replace(" ", "") == squashed]
        if picked:
            courses = picked

    if not courses:
        return KnowledgeAnswer(
            "That course code is not in the catalogue I hold. Codes I know: "
            + ", ".join(c["code"] for c in load()["courses"])
            + ".",
            source="ontology - Course",
        )

    lines = ["**Course information**", ""]
    for course in courses:
        lines.append(f"- **{course['code']} {course['title']}** ({course['units']} units)")
        prereq = (
            ", ".join(course["prerequisites"])
            if course["prerequisites"]
            else "none"
        )
        lines.append(f"  - Prerequisite: {prereq}")
        lines.append(f"  - Offered in: {', '.join(course['offered_in'])}")
        if course["laboratory"]:
            lines.append("  - Has a laboratory component")
        program = programs.get(course["part_of"])
        if program:
            lines.append(f"  - Part of {program['name']} ({program['max_units']} units total)")
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - Course",
        records=courses,
        draft=any(_is_draft(c) for c in courses),
    )


def answer_clearance() -> KnowledgeAnswer:
    service = next(s for s in load()["services"] if s["id"] == "clearance")
    guidance = next(o for o in load()["offices"] if o["id"] == "guidance")
    lines = [f"**{service['name']} - step by step**", ""]
    for index, step in enumerate(service["steps"], start=1):
        lines.append(f"{index}. {step}")
    lines += [
        "",
        f"**Where:** {guidance['name']} - {guidance['location']}, {guidance['hours']}.",
        "Bring your Form 138 and a down payment receipt if you still owe anything.",
    ]
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - Service",
        records=[service, guidance],
        draft=_is_draft(service),
    )


def greeting() -> KnowledgeAnswer:
    meta = load()["meta"]
    return KnowledgeAnswer(
        f"**Good day from the {meta['school']}**\n\n"
        "I can answer questions about enrollment requirements, deadlines, fees, "
        "office hours, course prerequisites and clearance, and I can check whether "
        "you are ready to enroll.\n\n"
        "_I never ask for your name, ID number, grades or contact details. "
        "Please do not type them here._",
        source="conversation - greeting",
    )


def handoff_note() -> KnowledgeAnswer:
    registrar = next(o for o in load()["offices"] if o["id"] == "registrar")
    return KnowledgeAnswer(
        f"**Handing you over to a staff member.**\n\n"
        f"{registrar['name']} - {registrar['location']}\n{registrar['hours']}\n\n"
        "_A summary of this chat (without any personal detail) is prepared for the "
        "staff member. You can also ask a question in the chat again at any time._",
        source="conversation - hand-off",
        records=[registrar],
    )


def search(question: str, limit: int = 3) -> list[dict]:
    """Find ontology records whose text overlaps the question.

    The fixed handlers below only know the six intents they were written for.
    This is the fallback for everything else: it scores every record in every
    section against the question's words, so a question nobody wrote a handler
    for can still reach the answer that already exists in the ontology.

    Scoring is deliberately simple and inspectable - shared word count with a
    bonus for a phrase match. No model, no embeddings, so a wrong hit can be
    traced to the words that caused it.
    """
    words = {w for w in re.findall(r"[a-z0-9]+", (question or "").lower()) if len(w) > 2}
    if not words:
        return []

    hits: list[dict] = []
    flat = question.lower()
    for section, records in load().items():
        if section == "meta" or not isinstance(records, list):
            continue
        for record in records:
            blob = json.dumps(record, ensure_ascii=False).lower()
            overlap = sum(1 for w in words if w in blob)
            if not overlap:
                continue
            name = record.get("name") or record.get("label") or record.get("code") or ""
            phrase_bonus = 3 if name and str(name).lower() in flat else 0
            hits.append(
                {
                    "section": section,
                    "score": overlap + phrase_bonus,
                    "record": record,
                }
            )

    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


def answer_from_search(question: str) -> KnowledgeAnswer | None:
    """Build an answer from the best ontology match, or None when nothing fits.

    Returns None rather than a vague guess: the caller then says it does not
    know, which is more useful than a confident wrong answer.
    """
    hits = search(question)
    if not hits or hits[0]["score"] < 3:
        return None

    lines = ["**Closest matches in the knowledge base**", ""]
    records = []
    for hit in hits:
        record = hit["record"]
        name = record.get("name") or record.get("label") or record.get("code") or hit["section"]
        detail_parts = []
        for key in ("description", "statement", "text", "location", "hours", "date", "amount"):
            if record.get(key):
                value = record[key]
                detail_parts.append(
                    f"PHP {value:,}" if key == "amount" and isinstance(value, int) else str(value)
                )
        lines.append(f"- **{name}** _({hit['section']})_")
        if detail_parts:
            lines.append("  - " + " - ".join(detail_parts))
        records.append(record)

    if any(_is_draft(r) for r in records):
        lines += ["", _draft_banner()]
    return KnowledgeAnswer(
        "\n".join(lines),
        source="ontology - keyword search",
        records=records,
        draft=any(_is_draft(r) for r in records),
    )


def answer_for(intent: str, entities) -> KnowledgeAnswer:
    """Route an intent to its ontology class, then fall back to search."""
    if intent == "ask_requirements":
        return answer_requirements(entities.student_type)
    if intent == "ask_schedule_deadline":
        keyword = None
        raw = (entities.raw or "").lower()
        for word in ("class", "payment", "scholarship", "add", "drop", "enrollment"):
            if word in raw:
                keyword = word
                break
        return answer_schedule(keyword)
    if intent == "ask_fees_payment":
        return answer_fees()
    if intent == "ask_office_hours_location":
        return answer_office(entities.office)
    if intent == "ask_course_prereq":
        return answer_course(entities.course_code)
    if intent == "ask_clearance_process":
        return answer_clearance()

    # No handler for this intent: search the whole ontology instead of giving
    # up. This is what makes the assistant answer beyond the six fixed topics.
    found = answer_from_search(entities.raw or "")
    if found is not None:
        return found
    return KnowledgeAnswer("I do not have an answer for that yet.", source="knowledge")
