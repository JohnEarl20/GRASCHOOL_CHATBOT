"""Backend orchestration for student-to-staff handoffs and AI fallback."""
from __future__ import annotations

from typing import Any

from code import conversation, dialogue


def request_staff_response(conversation_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Queue an owned student conversation for staff and append its notice."""
    updated = conversation.update_conversation_status(conversation_id, "waiting")
    if updated is None:
        raise ValueError("This conversation is no longer available.")
    notice = conversation.add_message(
        conversation_id,
        "assistant",
        "Your request has been sent to the staff queue. A staff member can reply here.",
        meta={
            "intent": "staff_requested",
            "source": "student-requested staff support",
        },
    )
    if notice is None:
        raise ValueError("The request was queued, but its confirmation could not be saved.")
    return updated, notice


def generate_timeout_fallback(
    conversation_id: str,
    student_id: str,
    policy: dialogue.Policy,
) -> dict[str, Any] | None:
    """Generate and save the AI response if the owned staff request timed out."""
    if not student_id:
        raise PermissionError("A student account is required for AI fallback.")
    conv = conversation.get_conversation(conversation_id)
    if not conv or conv.get("student_id") != student_id:
        raise PermissionError("You can only generate a fallback for your own conversation.")
    waiting_since = conv.get("waiting_since")
    if not isinstance(waiting_since, str):
        return None
    if conversation.staff_response_seconds_remaining(conv) != 0:
        return None
    if conversation.get_available_staff():
        return None

    last_question = next(
        (
            str(message.get("text", "")).strip()
            for message in reversed(conv.get("messages", []))
            if isinstance(message, dict)
            and message.get("role") in {"student", "user"}
            and str(message.get("text", "")).strip()
        ),
        "",
    )
    if not last_question:
        raise ValueError("Could not find the question for the AI fallback.")

    session = dialogue.new_session()
    session.session_id = conversation_id
    reply = dialogue.handle(
        last_question,
        session,
        policy=policy,
        student_id=student_id,
        student_name=conv.get("student_name"),
    )
    return conversation.add_staff_timeout_reply(
        conversation_id,
        waiting_since,
        reply.text,
        {
            "intent": reply.intent,
            "confidence": reply.confidence,
            "source": "AI fallback after staff response timeout",
            "answered": reply.answered,
            "escalated": reply.escalated,
            "staff_timeout_fallback": True,
        },
    )
