"""Test suite for the Cognitive Campus Assistant.

    python -m pytest tests/ -q          (if pytest is installed)
    python tests/test_app.py             (plain runner, no dependency)

Three groups:

1. Rule cases - 20 hand-made cases over the rule base, the "100% of 20
   hand-made cases" target of proposal section 13.
2. Agreement - the ontology and the rule base must agree about which
   documents each student type needs.
3. Conversation - the confidence policy, session memory, hand-off and the
   entity extraction behind them.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import rules_trace
from code import dialogue, knowledge, nlu

PASSED = 0
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{name} {detail}".strip())


# --------------------------------------------------------------------------
# 1. Rule cases
# --------------------------------------------------------------------------
def run(facts: set) -> set:
    final, _ = rules_trace.forward(facts)
    return final


def test_rule_cases() -> None:
    cases = [
        # (name, facts, must contain, must not contain)
        (
            "freshman with both documents and fees paid",
            {("student_type", "freshman"), ("has", "form138"), ("has", "psa_birth_certificate"), ("fees_paid",)},
            [("eligible", "official_enrollment")],
            [("docs_incomplete",)],
        ),
        (
            "freshman with both documents, no payment",
            {("student_type", "freshman"), ("has", "form138"), ("has", "psa_birth_certificate")},
            [("next_step", "pay_assessment")],
            [("eligible", "official_enrollment")],
        ),
        (
            "freshman with only form138",
            {("student_type", "freshman"), ("has", "form138")},
            [("missing", "psa_birth_certificate"), ("docs_incomplete",)],
            [("missing", "form138")],
        ),
        (
            "freshman with nothing",
            {("student_type", "freshman")},
            [("missing", "form138"), ("missing", "psa_birth_certificate"), ("next_step", "submit_missing_documents")],
            [("docs_complete",)],
        ),
        (
            "transferee with tor only",
            {("student_type", "transferee"), ("has", "tor")},
            [("missing", "honorable_dismissal"), ("next_step", "submit_missing_documents")],
            [("missing", "tor"), ("eligible", "official_enrollment")],
        ),
        (
            "transferee with tor and dismissal, fees paid",
            {("student_type", "transferee"), ("has", "tor"), ("has", "honorable_dismissal"), ("fees_paid",)},
            [("eligible", "official_enrollment")],
            [("docs_incomplete",)],
        ),
        (
            "transferee with dismissal only",
            {("student_type", "transferee"), ("has", "honorable_dismissal")},
            [("missing", "tor")],
            [("missing", "honorable_dismissal")],
        ),
        (
            "returning with clearance",
            {("student_type", "returning"), ("has", "clearance")},
            [("next_step", "pay_assessment")],
            [("missing", "clearance")],
        ),
        (
            "returning with clearance and fees paid",
            {("student_type", "returning"), ("has", "clearance"), ("fees_paid",)},
            [("eligible", "official_enrollment")],
            [("docs_incomplete",)],
        ),
        (
            "returning without clearance",
            {("student_type", "returning")},
            [("missing", "clearance"), ("next_step", "submit_missing_documents")],
            [("eligible", "official_enrollment")],
        ),
        (
            "fees paid but documents missing",
            {("student_type", "freshman"), ("fees_paid",)},
            [("next_step", "submit_missing_documents")],
            [("eligible", "official_enrollment")],
        ),
        (
            "no student type at all",
            {("fees_paid",)},
            [],
            [("docs_complete",), ("eligible", "official_enrollment")],
        ),
        (
            "transferee with tor, dismissal and form138",
            {("student_type", "transferee"), ("has", "tor"), ("has", "honorable_dismissal"), ("has", "form138"), ("fees_paid",)},
            [("eligible", "official_enrollment")],
            [("missing", "tor")],
        ),
        (
            "returning with clearance and tor",
            {("student_type", "returning"), ("has", "clearance"), ("has", "tor")},
            [("next_step", "pay_assessment")],
            [("missing", "clearance")],
        ),
        (
            "freshman complete, payment missing is not a document",
            {("student_type", "freshman"), ("has", "form138"), ("has", "psa_birth_certificate")},
            [("docs_complete",)],
            [("missing", "form138"), ("missing", "psa_birth_certificate")],
        ),
        (
            "transferee missing everything, fees paid",
            {("student_type", "transferee"), ("fees_paid",)},
            [("missing", "tor"), ("missing", "honorable_dismissal")],
            [("eligible", "official_enrollment")],
        ),
        (
            "returning with clearance, freshman documents too",
            {("student_type", "returning"), ("has", "clearance"), ("has", "form138"), ("fees_paid",)},
            [("eligible", "official_enrollment")],
            [("missing", "clearance")],
        ),
        (
            "freshman with psa only",
            {("student_type", "freshman"), ("has", "psa_birth_certificate")},
            [("missing", "form138")],
            [("missing", "psa_birth_certificate")],
        ),
        (
            "transferee with tor, no fees",
            {("student_type", "transferee"), ("has", "tor"), ("has", "honorable_dismissal")},
            [("next_step", "pay_assessment")],
            [("eligible", "official_enrollment"), ("docs_incomplete",)],
        ),
        (
            "returning without clearance, fees paid",
            {("student_type", "returning"), ("fees_paid",)},
            [("missing", "clearance"), ("next_step", "submit_missing_documents")],
            [("eligible", "official_enrollment")],
        ),
    ]
    for name, facts, must_have, must_not in cases:
        final = run(set(facts))
        for expected in must_have:
            check(f"[rule] {name}", expected in final, f"expected {expected} in the conclusion")
        for forbidden in must_not:
            check(f"[rule] {name}", forbidden not in final, f"did not expect {forbidden}")


# --------------------------------------------------------------------------
# 2. The ontology and the rule base must agree
# --------------------------------------------------------------------------
def test_ontology_agreement() -> None:
    expected = {
        "freshman": {"form138", "psa_birth_certificate"},
        "transferee": {"tor", "honorable_dismissal"},
        "returning": {"clearance"},
    }
    for student_type, docs in expected.items():
        check(
            f"[agreement] {student_type} requirements",
            set(knowledge.required_documents(student_type)) == docs,
            f"ontology says {knowledge.required_documents(student_type)}",
        )
        # The rule base must derive exactly these as "needed".
        final = run({("student_type", student_type)})
        derived = {f[1] for f in final if f[0] == "needs"}
        check(f"[agreement] {student_type} rules", derived == docs, f"rules derive {derived}")


# --------------------------------------------------------------------------
# 3. Entity extraction
# --------------------------------------------------------------------------
def test_nlu() -> None:
    entities = nlu.extract("I am a transferee and I have my TOR")
    check("[nlu] student type", entities.student_type == "transferee", str(entities.student_type))
    check("[nlu] holds tor", "tor" in entities.documents_held, str(entities.documents_held))

    entities = nlu.extract("i dont have clearance but i have my tor")
    check("[nlu] missing clearance", "clearance" in entities.documents_missing, str(entities.documents_missing))
    check("[nlu] still holds tor", "tor" in entities.documents_held, str(entities.documents_held))

    entities = nlu.extract("wala akong clearance")
    check("[nlu] filipino negation", "clearance" in entities.documents_missing, str(entities.documents_missing))

    entities = nlu.extract("do i need a birth certificate to enroll?")
    check("[nlu] question does not change holdings", not entities.documents_held, str(entities.documents_held))

    entities = nlu.extract("Can I enroll? Transferee ako, may TOR")
    check("[nlu] statement after a question counts", "tor" in entities.documents_held, str(entities.documents_held))
    check("[nlu] type after a question counts", entities.student_type == "transferee", str(entities.student_type))

    entities = nlu.extract("TOR lang")
    check("[nlu] bare mention means held", "tor" in entities.documents_held, str(entities.documents_held))

    entities = nlu.extract("I already paid my fees")
    check("[nlu] fees paid", entities.fees_paid is True, str(entities.fees_paid))

    entities = nlu.extract("hindi ko pa bayad ang fees")
    check("[nlu] fees not paid", entities.fees_paid is False, str(entities.fees_paid))

    entities = nlu.extract("what is the prerequisite of CS 201")
    check("[nlu] course code", entities.course_code == "CS 201", str(entities.course_code))


# --------------------------------------------------------------------------
# 4. Conversation behaviour
# --------------------------------------------------------------------------
def test_dialogue() -> None:
    session = dialogue.new_session()
    reply = dialogue.handle("Can I enroll? I am a transferee and I have my TOR", session)
    check("[chat] eligibility asked for the type or answered",
          "submit" in reply.text.lower() or "honorable" in reply.text.lower(), reply.text[:120])
    check("[chat] rules fired", "R3" in reply.rules_fired, str(reply.rules_fired))
    check("[chat] session remembers the type", session.student_type == "transferee", str(session.student_type))

    session = dialogue.new_session()
    reply = dialogue.handle("Can I enroll?", session)
    check("[chat] clarifies the student type", reply.clarified and session.pending == "student_type", reply.text[:120])
    check("[chat] options offered", len(reply.options) == 3, str(reply.options))

    session = dialogue.new_session()
    dialogue.handle("Can I enroll? I am a freshman and I have my Form 138 and PSA", session)
    check("[chat] session remembers documents", "form138" in session.documents_held, str(session.documents_held))

    session = dialogue.new_session()
    reply = dialogue.handle("qqqq zzzz", session)
    check("[chat] unknown input is a fallback", not reply.answered and reply.source.endswith("fallback"), reply.source)

    session = dialogue.new_session()
    dialogue.handle("qqqq zzzz", session)
    reply = dialogue.handle("qqqq zzzz", session)
    check("[chat] two misses hand off", reply.escalated, str(reply.escalated))

    session = dialogue.new_session()
    reply = dialogue.handle("I want to talk to a staff member", session)
    check("[chat] hand-off on request", reply.escalated and "Handing you over" in reply.text, reply.text[:80])

    session = dialogue.new_session()
    reply = dialogue.handle("What do I need to enroll as a freshman?", session)
    check("[chat] ontology answer", "Form 138" in reply.text and "PSA" in reply.text, reply.text[:120])
    check("[chat] ontology source", reply.source.startswith("ontology"), reply.source)

    session = dialogue.new_session()
    reply = dialogue.handle("When is the payment deadline?", session)
    check("[chat] deadline answer", "payment" in reply.text.lower(), reply.text[:120])

    session = dialogue.new_session()
    reply = dialogue.handle("What is the prerequisite of CS 201?", session)
    check("[chat] course answer", "CS 102" in reply.text, reply.text[:160])


def main() -> int:
    test_rule_cases()
    test_ontology_agreement()
    test_nlu()
    test_dialogue()

    print(f"checks passed: {PASSED}")
    if FAILED:
        print(f"checks failed: {len(FAILED)}")
        for line in FAILED:
            print("  FAIL:", line)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
