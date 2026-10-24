"""Reasoning layer: backward chaining - "why can I not enroll yet?"

Forward chaining (the root rules_trace.py) answers "what is true now". This
module answers the other half of the student's question: which fact is
blocking the goal and which rule says so. It walks the rule base backwards
from the goal, reusing the matcher from rules_trace so both directions read
the rule base the same way.

Worked example from proposal section 8:

    goal eligible(official_enrollment)
      R11 needs docs_complete and fees_paid
      docs_complete comes from R9, which needs has(tor) and
      has(honorable_dismissal); the first is true, the second is not
      => the blocking fact is the missing honorable dismissal
"""
from __future__ import annotations

from dataclasses import dataclass

from rules_trace import RULES, match

GOAL = ("eligible", "official_enrollment")


@dataclass
class Blocker:
    """One unmet condition on the way to the goal."""

    rule_id: str
    conclusion: tuple
    fact: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "fact": self.fact,
            "reason": self.reason,
        }


def _condition_text(cond: tuple) -> str:
    """Render a condition the way the rule base writes it."""
    if len(cond) == 1:
        return str(cond[0])
    return f"{cond[0]}({cond[1]})"


def _producers_of(condition: tuple) -> list[str]:
    return [rid for rid, _, concl in RULES if tuple(concl) == tuple(condition)]


def _blockers_for_rule(rule_id: str, facts: set) -> list[Blocker]:
    """The unsatisfied conditions inside one rule."""
    out: list[Blocker] = []
    for rid, conds, concl in RULES:
        if rid != rule_id:
            continue
        # A rule written for a different student type does not apply here, so
        # its unsatisfied conditions are not blockers for this student.
        student_conditions = [c for c in conds if c[0] == "student_type"]
        if student_conditions and not any(match(c, facts, {}) for c in student_conditions):
            return []
        for cond in conds:
            if cond[0] == "not":
                # A negated condition blocks the rule when the pattern IS present.
                if tuple(cond[1]) in facts:
                    out.append(
                        Blocker(
                            rule_id=rid,
                            conclusion=tuple(concl),
                            fact=str(cond[1][1] if len(cond[1]) > 1 else cond[1][0]),
                            reason=f"{rid} cannot fire because {cond[1][0]}({cond[1][1]}) is present.",
                        )
                    )
                continue
            if match(cond, facts, {}):
                continue
            fact_name = str(cond[1]) if len(cond) > 1 else str(cond[0])
            out.append(
                Blocker(
                    rule_id=rid,
                    conclusion=tuple(concl),
                    fact=fact_name,
                    reason=f"{rid} needs {_condition_text(cond)}, which is not in the facts.",
                )
            )
    return out


def blocking_facts(facts: set, goal: tuple = GOAL) -> list[Blocker]:
    """Every fact that stands between the current facts and the goal."""
    facts = set(facts)
    blockers: list[Blocker] = []
    for rid, conds, concl in RULES:
        if tuple(concl) != tuple(goal):
            continue
        for cond in conds:
            if match(cond, facts, {}):
                continue
            if cond[0] == "not":
                if tuple(cond[1]) in facts:
                    blockers.extend(_blockers_for_rule(rid, facts))
                continue
            producers = _producers_of(cond)
            if not producers:
                blockers.append(
                    Blocker(
                        rule_id=rid,
                        conclusion=tuple(concl),
                        fact=str(cond[1]) if len(cond) > 1 else str(cond[0]),
                        reason=f"{rid} needs {_condition_text(cond)}, which nothing in the rule base can produce.",
                    )
                )
                continue
            for producer in producers:
                blockers.extend(_blockers_for_rule(producer, facts))
    return blockers


def explain_blocking(facts: set, labels: dict | None = None) -> list[str]:
    """Human sentences for the blockers, with document names in plain language."""
    labels = labels or {}
    lines = []
    for blocker in blocking_facts(facts):
        pretty = labels.get(blocker.fact, blocker.fact)
        lines.append(f"{blocker.reason} You still need: {pretty}.")
    return lines
