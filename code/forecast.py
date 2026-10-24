"""Analytics layer: weekly volume forecast and the staff recommendation.

Proposal section 10 compares a moving average against ARIMA and picks the
moving average: there is little data, so the simplest explainable method
wins. The recommendation always carries its evidence and a confidence, so a
staff member sees why before acting (proposal section 6, F6).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

WINDOW = 3


def _week_key(ts: str) -> str:
    """ISO week label of a timestamp."""
    try:
        date = datetime.fromisoformat(ts).date()
    except (TypeError, ValueError):
        return "unknown"
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def _day_key(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%A")
    except (TypeError, ValueError):
        return "unknown"


def weekly_counts(logs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in logs:
        counts[_week_key(row.get("ts", ""))] += 1
    return dict(sorted(counts.items()))


def daily_counts(logs: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in logs:
        counts[_day_key(row.get("ts", ""))] += 1
    return dict(sorted(counts.items()))


def intent_counts(logs: list[dict]) -> dict[str, int]:
    counts = Counter(row.get("intent", "unknown") for row in logs)
    return dict(counts.most_common())


def unanswered(logs: list[dict]) -> list[dict]:
    """Turns the assistant could not answer - the review list for staff."""
    return [row for row in logs if not row.get("answered")]


def moving_average(values: list[float], window: int = WINDOW) -> float:
    """Forecast the next period as the mean of the last `window` periods."""
    if not values:
        return 0.0
    tail = values[-window:]
    return sum(tail) / len(tail)


def forecast_next_week(logs: list[dict]) -> dict:
    """Forecast next week's question volume from the weekly counts."""
    weekly = weekly_counts(logs)
    counts = list(weekly.values())
    forecast = moving_average(counts)
    last_week = counts[-1] if counts else 0
    if len(counts) < 2:
        return {
            "forecast": round(forecast, 1),
            "last_week": last_week,
            "weeks_of_history": len(counts),
            "method": f"moving average over the last {WINDOW} weeks",
            "reliable": False,
        }
    # Confidence in the forecast: how steady the weekly volume has been.
    spread = (max(counts) - min(counts)) / max(counts) if max(counts) else 0.0
    confidence = round(max(0.2, min(0.95, 1 - spread)), 2)
    return {
        "forecast": round(forecast, 1),
        "last_week": last_week,
        "weeks_of_history": len(counts),
        "method": f"moving average over the last {WINDOW} weeks",
        "confidence": confidence,
        "reliable": len(counts) >= 4,
    }


def recommend(logs: list[dict]) -> dict:
    """The staffing / announcement recommendation, with evidence and confidence."""
    if len(logs) < 20:
        return {
            "headline": "Not enough questions logged yet to recommend anything.",
            "evidence": f"Only {len(logs)} turns in the log so far.",
            "confidence": 0.0,
            "action": "Keep the assistant running and check again after a few days.",
        }

    weekly = weekly_counts(logs)
    counts = list(weekly.values())
    forecast = moving_average(counts)

    days = Counter(_day_key(row.get("ts", "")) for row in logs)
    busiest_day, busiest_count = days.most_common(1)[0]
    share = busiest_count / len(logs)

    intents = intent_counts(logs)
    top_intent, top_count = next(iter(intents.items()))
    intent_share = top_count / len(logs)

    unanswered_rows = unanswered(logs)
    unanswered_share = len(unanswered_rows) / len(logs)

    # The recommendation follows the biggest lever we can see.
    if share >= 0.3 and busiest_count >= 15:
        headline = f"Staff one extra person at the window on {busiest_day}."
        evidence = (
            f"{busiest_count} of {len(logs)} questions ({share:.0%}) arrived on a "
            f"{busiest_day}. Next week is forecast at about {forecast:.0f} questions."
        )
        action = "Move one staff member to the busiest day and post the wait time."
    elif unanswered_share >= 0.2:
        headline = "Update the announcements for the questions the assistant cannot answer."
        evidence = (
            f"{len(unanswered_rows)} of {len(logs)} questions ({unanswered_share:.0%}) "
            f"could not be answered. The most frequent topic was {top_intent} "
            f"({intent_share:.0%} of all questions)."
        )
        action = "Add the missing answers to the knowledge base and retrain the model."
    else:
        headline = f"Keep the current staffing - {top_intent} is the dominant topic."
        evidence = (
            f"{top_count} of {len(logs)} questions ({intent_share:.0%}) were about "
            f"{top_intent}. Weekly volume has been steady around {forecast:.0f}."
        )
        action = "Review the unanswered list weekly."

    # The confidence mixes two things: how much evidence stands behind the
    # claim, and how steady the volume forecast is. A recommendation that only
    # knows how many questions arrive is not the same as one that knows how
    # many are coming, so both have to be in the number.
    forecast_confidence = forecast_next_week(logs).get("confidence", 0.5)
    evidence_strength = min(1.0, busiest_count / 40)
    confidence = round(max(0.1, min(0.95, 0.5 * evidence_strength + 0.5 * forecast_confidence)), 2)

    return {
        "headline": headline,
        "evidence": evidence,
        "confidence": confidence,
        "action": action,
    }
