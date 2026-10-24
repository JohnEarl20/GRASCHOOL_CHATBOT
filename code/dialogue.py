"""Conversation layer: session memory, the confidence policy, and the hand-off.

Proposal section 11 fixes the confidence policy:

    probability >= 0.60  -> answer
    0.40 - 0.59          -> ask a clarifying question with buttons
    below 0.40           -> fallback message, and after two misses a hand-off

Proposal section 5 fixes the behaviour: the assistant remembers the student
type and the documents already mentioned during the session, so "TOR lang"
answers the second half of a two-turn eligibility check.

The eligibility answer itself comes from the rule base (rules_trace.py) - the
conversation layer never invents a conclusion, it only collects the facts and
explains the rules that fired.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import rules_trace
from code import explain, knowledge, logger, nlu
from code.intent_model import get_model as get_intent_model
from code.sentiment import get_model as get_sentiment_model

ANSWER_THRESHOLD = 0.60
CLARIFY_THRESHOLD = 0.40
MISSES_BEFORE_HANDOFF = 2

# The proposal's policy asks a clarifying question for everything between
# 0.40 and 0.59. With a 324-question corpus the model is often right but not
# confident ("What do I need to enroll as a freshman?" scored 0.59 for
# ask_requirements against 0.09 for the runner-up), and asking "do you mean
# requirements or deadlines?" there is worse than answering. So a top intent
# that beats the runner-up by this margin is answered anyway, and the answer
# card shows the real confidence and the margin.
DECISIVE_MARGIN = 0.25

STUDENT_TYPE_OPTIONS = [
    ("Freshman", "freshman"),
    ("Transferee", "transferee"),
    ("Returning student", "returning"),
]

AMBIGUOUS_INTENTS = {
    "ask_requirements": "requirements or deadlines",
    "ask_schedule_deadline": "requirements or deadlines",
    "ask_fees_payment": "fees or office hours",
    "ask_office_hours_location": "fees or office hours",
    "ask_course_prereq": "prerequisites or clearance",
    "ask_clearance_process": "prerequisites or clearance",
}


@dataclass
class Session:
    """What the assistant remembers for one student during one visit."""

    session_id: str
    student_type: str | None = None
    documents_held: set[str] = field(default_factory=set)
    documents_missing: set[str] = field(default_factory=set)
    fees_paid: bool | None = None
    misses: int = 0
    pending: str | None = None
    escalated: bool = False
    turns: int = 0

    def as_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "student_type": self.student_type,
            "documents_held": sorted(self.documents_held),
            "documents_missing": sorted(self.documents_missing),
            "fees_paid": self.fees_paid,
            "turns": self.turns,
        }


@dataclass
class Reply:
    text: str
    intent: str
    confidence: float
    source: str
    rules_fired: list[str] = field(default_factory=list)
    facts: list[tuple] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    clarified: bool = False
    options: list[str] = field(default_factory=list)
    answered: bool = True
    escalated: bool = False
    sentiment: str | None = None
    decisive: bool = False
    margin: float = 0.0


def new_session() -> Session:
    return Session(session_id=uuid.uuid4().hex[:12])


@dataclass(frozen=True)
class Policy:
    """The confidence policy in force for one call.

    The three numbers come from the proposal (section 11) and are the defaults
    here. The Settings page can override them for a session; a caller that
    passes nothing gets the defaults, so the rule base and the tests keep the
    documented behaviour.
    """

    answer_threshold: float = ANSWER_THRESHOLD
    clarify_threshold: float = CLARIFY_THRESHOLD
    decisive_margin: float = DECISIVE_MARGIN
    misses_before_handoff: int = MISSES_BEFORE_HANDOFF

    def __post_init__(self) -> None:
        # Fail closed on a nonsensical pair rather than silently answering
        # everything or nothing.
        if not 0.0 <= self.clarify_threshold < self.answer_threshold <= 1.0:
            raise ValueError(
                "clarify_threshold must be below answer_threshold, both within 0..1 "
                f"(got clarify={self.clarify_threshold}, answer={self.answer_threshold})"
            )


def _log(text: str, reply: Reply, session: Session) -> None:
    logger.log_turn(
        {
            "session_id": session.session_id,
            "text": text,
            "intent": reply.intent,
            "confidence": reply.confidence,
            "answered": reply.answered,
            "clarified": reply.clarified,
            "source": reply.source,
            "rules_fired": reply.rules_fired,
            "facts": [list(f) for f in reply.facts],
            "escalated": reply.escalated,
            "sentiment": reply.sentiment,
            "student_type": session.student_type,
        }
    )


def _update_session(session: Session, entities: nlu.Entities) -> None:
    """Fold what the student just said into the session memory."""
    if entities.student_type:
        session.student_type = entities.student_type
    for doc in entities.documents_held:
        session.documents_missing.discard(doc)
        session.documents_held.add(doc)
    for doc in entities.documents_missing:
        session.documents_held.discard(doc)
        session.documents_missing.add(doc)
    if entities.fees_paid is not None:
        session.fees_paid = entities.fees_paid
    if entities.says_all_documents and session.student_type:
        session.documents_held.update(knowledge.required_documents(session.student_type))


def _clarify_student_type(session: Session, intent: str, confidence: float) -> Reply:
    session.pending = "student_type"
    options = [label for label, _ in STUDENT_TYPE_OPTIONS]
    return Reply(
        text=(
            "To check that, I need to know which one you are:\n\n"
            "- **Freshman** - new or first year student\n"
            "- **Transferee** - you studied in another school\n"
            "- **Returning student** - you are re-enrolling here\n\n"
            "_I never ask for your name or ID number - only the student type._"
        ),
        intent=intent,
        confidence=confidence,
        source="conversation - clarification",
        clarified=True,
        options=options,
        answered=True,
    )


def _clarify_ambiguity(intent: str, confidence: float, prediction) -> Reply:
    alternatives = [name for name, _ in prediction.alternatives]
    guess = AMBIGUOUS_INTENTS.get(intent)
    if guess:
        text = f"I am not sure what you are asking about. Do you mean **{guess}**?"
    else:
        text = "I am not sure what you are asking about."
    if alternatives:
        text += f" My best guesses: {', '.join(alternatives)}."
    return Reply(
        text=text,
        intent=intent,
        confidence=confidence,
        source="conversation - clarification",
        clarified=True,
        options=alternatives,
        answered=True,
    )


def _eligibility(session: Session, intent: str, confidence: float) -> Reply:
    """Run the rule base and explain the result."""
    if not session.student_type:
        return _clarify_student_type(session, intent, confidence)

    facts: set[tuple] = {("student_type", session.student_type)}
    for doc in sorted(session.documents_held):
        facts.add(("has", doc))
    if session.fees_paid:
        facts.add(("fees_paid",))

    final, trace = rules_trace.forward(facts)
    fired = [rid for _, rid, _, _ in trace]
    blockers = explain.explain_blocking(final, knowledge.FACT_LABELS)

    missing = sorted(f for f in final if f[0] == "missing")
    missing_names = [knowledge.DOCUMENT_LABELS.get(f[1], f[1]) for f in missing]

    if ("eligible", "official_enrollment") in final:
        text = (
            f"**You are ready for official enrollment.**\n\n"
            f"Your {session.student_type} requirements are complete and the assessment "
            f"is on record, so the rule base concludes `eligible(official_enrollment)`."
        )
    elif ("next_step", "pay_assessment") in final:
        text = (
            "**Your documents are complete - the next step is to pay the assessment.**\n\n"
            "The rule base concludes `next_step(pay_assessment)`: the requirements are "
            "complete, but no payment is on record yet."
        )
        if session.fees_paid is None:
            text += "\n\n_I have not been told whether you already paid. If you did, say so and I will re-check._"
    else:
        text = "**Not yet - you still need to submit a document.**"
        if missing_names:
            listing = "\n".join(f"- {name}" for name in missing_names)
            text += f"\n\nStill missing:\n{listing}"
        text += "\n\nThe rule base concludes `next_step(submit_missing_documents)`."

    if blockers and ("eligible", "official_enrollment") not in final:
        text += "\n\n**Why this answer**\n"
        text += "\n".join(f"- {line}" for line in blockers)

    text += (
        f"\n\n_Rules fired: {', '.join(fired) if fired else 'none'}._\n"
        f"_Source: the rule base in `rules_trace.py` (R1-R13)._"
    )

    return Reply(
        text=text,
        intent=intent,
        confidence=confidence,
        source="rules - forward chaining",
        rules_fired=fired,
        facts=sorted(final),
        blockers=blockers,
        answered=True,
    )


def _handoff(session: Session, intent: str, confidence: float) -> Reply:
    session.escalated = True
    note = knowledge.handoff_note()
    return Reply(
        text=note.text,
        intent=intent,
        confidence=confidence,
        source="conversation - hand-off",
        answered=True,
        escalated=True,
    )


def _feedback_reply(text: str, session: Session, intent: str, confidence: float) -> Reply:
    prediction = get_sentiment_model().predict(text)
    if prediction.sentiment == "negative":
        body = (
            "**Sorry about that - I am glad you told me.**\n\n"
            "Your comment is logged for the registrar staff, and they read every "
            "unanswered and badly answered question. Ask for a staff member and I "
            "will hand you over."
        )
    elif prediction.sentiment == "positive":
        body = "**Thank you - that helps.**\n\nYour comment is logged for the registrar staff."
    else:
        body = "**Noted.**\n\nYour comment is logged for the registrar staff."
    return Reply(
        text=body,
        intent=intent,
        confidence=confidence,
        source="sentiment model - feedback",
        answered=True,
        sentiment=prediction.sentiment,
    )


def _margin(prediction) -> float:
    """How far the top intent is ahead of the runner-up."""
    if not prediction.alternatives:
        return prediction.confidence
    return round(prediction.confidence - prediction.alternatives[0][1], 4)


def _is_decisive(prediction, margin: float = DECISIVE_MARGIN) -> bool:
    """True when the top intent is clearly ahead of every other one."""
    return _margin(prediction) >= margin


def handle(text: str, session: Session, policy: "Policy | None" = None) -> Reply:
    """Handle one student message and return the assistant's reply.

    `policy` overrides the module defaults for this call. The Settings page
    passes a Policy built from its sliders, so moving a slider changes what
    the assistant actually does rather than only what the panel displays.
    Passing None keeps the defaults in this module.
    """
    policy = policy or Policy()
    session.turns += 1
    text = (text or "").strip()

    if not text:
        session.misses += 1
        reply = Reply(
            text=(
                "I did not catch that. Ask me about enrollment requirements, deadlines, "
                "fees, office hours, course prerequisites or clearance - or tell me "
                "your student type and documents and I will check if you can enroll."
            ),
            intent="empty_input",
            confidence=0.0,
            source="conversation - fallback",
            answered=False,
        )
        if session.misses >= policy.misses_before_handoff:
            reply.text += "\n\n" + knowledge.handoff_note().text
            reply.escalated = True
            session.escalated = True
        _log(text, reply, session)
        return reply

    entities = nlu.extract(text)
    prediction = get_intent_model().predict(text)
    _update_session(session, entities)

    if prediction.confidence < policy.clarify_threshold:
        # Before giving up, try the ontology: the intent model can be unsure
        # about a question the knowledge base actually answers ("Where do I get
        # the scholarship form" scored 0.19 while the ontology held the
        # scholarship record). A confident ontology match beats a fallback.
        found = knowledge.answer_from_search(text)
        if found is not None:
            reply = Reply(
                text=found.text + ("\n\n" + knowledge._draft_banner() if found.draft else ""),
                intent=prediction.intent,
                confidence=prediction.confidence,
                source=found.source,
                answered=True,
            )
            reply.decisive = _is_decisive(prediction, policy.decisive_margin)
            reply.margin = _margin(prediction)
            _log(text, reply, session)
            return reply

        session.misses += 1
        reply = Reply(
            text=(
                "I am not sure I understood that one. I can help with enrollment "
                "requirements, deadlines, fees, office hours, prerequisites, "
                "clearance, and with checking whether you can enroll.\n\n"
                "Try one of these:\n"
                "- What do I need to enroll as a freshman?\n"
                "- Can I enroll? I am a transferee and I have my TOR\n"
                "- When is the payment deadline?"
            ),
            intent=prediction.intent,
            confidence=prediction.confidence,
            source="conversation - fallback",
            answered=False,
        )
        if session.misses >= policy.misses_before_handoff:
            reply.text += "\n\n" + knowledge.handoff_note().text
            reply.escalated = True
            session.escalated = True
    elif prediction.confidence < policy.answer_threshold and not _is_decisive(
        prediction, policy.decisive_margin
    ):
        if prediction.intent == "check_eligibility" and not session.student_type:
            reply = _clarify_student_type(session, prediction.intent, prediction.confidence)
        else:
            reply = _clarify_ambiguity(prediction.intent, prediction.confidence, prediction)
    elif prediction.intent == "greet":
        answer = knowledge.greeting()
        reply = Reply(
            text=answer.text,
            intent="greet",
            confidence=prediction.confidence,
            source="conversation - greeting",
            answered=True,
        )
    elif prediction.intent == "request_human":
        reply = _handoff(session, prediction.intent, prediction.confidence)
    elif prediction.intent == "give_feedback":
        reply = _feedback_reply(text, session, prediction.intent, prediction.confidence)
    elif prediction.intent == "check_eligibility":
        reply = _eligibility(session, prediction.intent, prediction.confidence)
    else:
        answer = knowledge.answer_for(prediction.intent, entities)
        reply = Reply(
            text=answer.text + ("\n\n" + knowledge._draft_banner() if answer.draft else ""),
            intent=prediction.intent,
            confidence=prediction.confidence,
            source=answer.source,
            answered=True,
        )

    reply.decisive = _is_decisive(prediction, policy.decisive_margin)
    reply.margin = _margin(prediction)
    _log(text, reply, session)
    return reply


def log_feedback(session: Session, text: str, value: str) -> None:
    """Record a thumbs up / thumbs down on one answer."""
    logger.log_turn(
        {
            "session_id": session.session_id,
            "event": "feedback",
            "text": text,
            "intent": "give_feedback",
            "confidence": None,
            "answered": True,
            "feedback": value,
        }
    )
