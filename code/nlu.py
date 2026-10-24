"""Ingestion layer: preprocessing and entity extraction.

Deterministic and offline on purpose: lowercase, drop Taglish particles, then
read entities out of the remaining tokens with a small state machine. No model
and no network call, so every slot in an answer can be traced back to the
words the student actually typed.

Two token streams are used on purpose:

    normalize()  the text the intent model sees (Taglish particles removed)
    _tokens()    the raw lowercased tokens the state machine reads, because
                 negation words ("hindi", "wala", "dont") must survive

How possession is read
-----------------------
A document mentioned in a *declarative* fragment is treated as held unless the
fragment says otherwise ("i dont have clearance" -> missing). A document
mentioned in an *interrogative* fragment ("do i need a birth certificate?") is
informational only and never changes what the student is believed to hold -
otherwise asking a question would silently add a missing document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Taglish particles and filler that carry no intent signal. Negation words are
# deliberately absent: the state machine needs them.
PARTICLES = {
    "po", "ba", "baka", "kasi", "naman", "sana", "pre", "sis", "dong", "daw",
    "pala", "rin", "lang", "nga", "opo", "ah", "eh", "oh", "ay", "yung",
    "mga", "natin", "ninyo", "kayo", "ako", "ikaw", "ito", "iyon", "para",
    "kung", "sige", "nako", "tulong", "yep", "nope", "pro", "fyi", "pls",
    "tnx", "thx", "kk", "lg", "mgd", "hmm", "mismo", "talaga",
}

# Cue words that flip the reading of the documents that follow them.
NEG_TOKENS = {
    "no", "not", "without", "missing", "lack", "lacking", "wala", "walang",
    "hindi", "di", "bawal", "ayoko", "none",
    # Apostrophes are stripped before tokenising, so the contractions arrive
    # without them ("i don't have X" -> "dont have X").
    "dont", "doesnt", "didnt", "cant", "couldnt", "wont", "wouldnt",
    "isnt", "arent", "wasnt", "werent", "havent", "hasnt", "shouldnt",
}
NEED_TOKENS = {"need", "needs", "needto", "kailangan", "kailangang", "submit", "submitting"}
POS_TOKENS = {
    "have", "has", "got", "with", "brought", "carry", "carried", "held",
    "holds", "may", "meron", "mayroon", "kinuha", "nakuha", "napasa",
}

QUESTION_WORDS = {
    "do", "does", "did", "can", "could", "is", "are", "am", "shall", "will",
    "would", "what", "when", "where", "why", "how", "which", "who", "whom",
    "whose", "bakit", "saan", "kailan", "ano", "magkano", "ilan", "sino",
    "may i", "can i",
}

STUDENT_TYPE_ALIASES = {
    "freshman": ("freshman", "freshmen", "first year", "firstyear", "new student", "bagong student"),
    "transferee": ("transferee", "transferees", "transfer student", "transferee student"),
    "returning": ("returning", "returning student", "returnee", "old student", "returning students"),
}

OFFICE_ALIASES = {
    "registrar": ("registrar", "registrars office", "registrar office"),
    "cashier": ("cashier", "cashiers office", "accounting", "accounting office"),
    "guidance": ("guidance", "guidance office", "counseling"),
    "library": ("library", "university library"),
    "osa": ("osa", "student affairs", "office of student affairs"),
    "clinic": ("clinic", "medical"),
}

# (alias tokens, canonical id) - longest alias first so "psa birth certificate"
# wins over a bare "psa" at the same position.
DOCUMENT_ALIASES = {
    "tor": (("tor",), ("transcript", "of", "records"), ("transcript",), ("tsr",)),
    "form138": (("form", "138"), ("form138",), ("school", "record")),
    "psa_birth_certificate": (
        ("psa", "birth", "certificate"), ("psa", "birth", "cert"),
        ("birth", "certificate"), ("birth", "cert"), ("psa",),
    ),
    "honorable_dismissal": (
        ("honorable", "dismissal"), ("honorable", "dismissals"), ("good", "moral", "character"),
    ),
    "clearance": (("clearance",),),
}

_ALIAS_INDEX = sorted(
    ((tuple(alias), doc) for doc, aliases in DOCUMENT_ALIASES.items() for alias in aliases),
    key=lambda pair: -len(pair[0]),
)

_FEE_WORDS = {"paid", "bayad", "bayaran", "payment", "payments"}
_ALL_DOCS_CUES = ("all my documents", "all documents", "everything", "lahat ng documents", "all of my documents")

_COURSE_RE = re.compile(r"\b([A-Za-z]{2,5})(\s+e(?:lec)?)?\s*(\d{1,3})\b")
_TERM_RE = re.compile(r"\b(1st|2nd|3rd|first|second|third)\s+semester\b")


@dataclass
class Entities:
    """Everything the ingestion layer could read out of one message."""

    student_type: str | None = None
    documents_held: set[str] = field(default_factory=set)
    documents_missing: set[str] = field(default_factory=set)
    fees_paid: bool | None = None
    office: str | None = None
    course_code: str | None = None
    term: str | None = None
    says_all_documents: bool = False
    interrogative: bool = False
    raw: str = ""


def normalize(text: str) -> str:
    """Text form handed to the intent model: lowercase, no punctuation, no particles."""
    t = (text or "").lower().replace("'", "").replace("’", "")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(w for w in t.split() if w and w not in PARTICLES)


def _tokens(text: str) -> list[str]:
    """Raw lowercased tokens - negation words and particles still present."""
    t = (text or "").lower().replace("'", "").replace("’", "")
    return re.findall(r"[a-z0-9]+", t)


def _fragments(text: str) -> list[str]:
    """Split a message into declaratives and questions.

    "Can I enroll? Transferee ako, may TOR" becomes three fragments, the
    first one a question and the other two statements - so the question does
    not erase the possession the student stated right after it.
    """
    parts = re.split(r"[.?!,;]+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _is_question(fragment: str) -> bool:
    first = _tokens(fragment)
    if not first:
        return False
    if first[0] in QUESTION_WORDS:
        return True
    two = " ".join(first[:2])
    return two in QUESTION_WORDS


def _match_alias(tokens: list[str], i: int) -> tuple[str, int] | None:
    """Longest document alias starting at token index i."""
    for alias, doc in _ALIAS_INDEX:
        if tokens[i : i + len(alias)] == list(alias):
            return doc, len(alias)
    return None


def _read_fragment(fragment: str, ent: Entities) -> None:
    """Update entity slots from one fragment."""
    tokens = _tokens(fragment)
    mode: str | None = None          # "have" | "not" | None
    suppress_next_pos = False        # "dont have X" - the "have" belongs to the negation
    i = 0
    while i < len(tokens):
        token = tokens[i]

        alias = _match_alias(tokens, i)
        if alias:
            doc, length = alias
            if mode == "not":
                ent.documents_missing.add(doc)
            elif mode == "have":
                ent.documents_held.add(doc)
            else:
                # A bare mention in a statement still means possession
                # ("TOR lang"), unless the fragment is a question.
                ent.documents_held.add(doc)
            i += length
            continue

        if token in NEG_TOKENS:
            mode = "not"
            suppress_next_pos = True
        elif token in NEED_TOKENS:
            mode = "not"
        elif token in POS_TOKENS:
            if suppress_next_pos:
                suppress_next_pos = False
            else:
                mode = "have"
        elif token in _FEE_WORDS:
            ent.fees_paid = mode != "not"
        elif token == "unpaid":
            ent.fees_paid = False

        i += 1


def _read_student_type(text: str, ent: Entities) -> None:
    flat = " ".join(_tokens(text))
    for canonical, aliases in STUDENT_TYPE_ALIASES.items():
        for alias in aliases:
            if alias in flat:
                ent.student_type = canonical
                return


def _read_office(text: str, ent: Entities) -> None:
    flat = " ".join(_tokens(text))
    for canonical, aliases in OFFICE_ALIASES.items():
        if any(alias in flat for alias in aliases):
            ent.office = canonical
            return


def _read_course_code(text: str, ent: Entities) -> None:
    for match in _COURSE_RE.finditer(text or ""):
        letters, elective, number = match.group(1), match.group(2), match.group(3)
        code = f"{letters.upper()}{' ELEC' if elective else ''} {number}"
        if letters.upper() in {"BSCS", "BSIT", "BSIS", "BSBA", "BSED"}:
            continue
        ent.course_code = code
        return


def _read_term(text: str, ent: Entities) -> None:
    match = _TERM_RE.search((text or "").lower())
    if match:
        word = match.group(1)
        ent.term = {
            "1st": "1st semester", "first": "1st semester",
            "2nd": "2nd semester", "second": "2nd semester",
            "3rd": "3rd semester", "third": "3rd semester",
        }[word]


def extract(text: str) -> Entities:
    """Read every entity the assistant can use out of one student message."""
    ent = Entities(raw=text or "")
    flat = " ".join(_tokens(text)).lower()

    for cue in _ALL_DOCS_CUES:
        if cue in flat:
            ent.says_all_documents = True
            break

    fragments = _fragments(text)
    ent.interrogative = bool(fragments) and all(_is_question(f) for f in fragments)

    for fragment in fragments:
        if _is_question(fragment):
            # A question mentions documents but does not change what is held.
            # Read only the student type and other non-possession slots.
            _read_student_type(fragment, ent)
            continue
        _read_fragment(fragment, ent)

    _read_student_type(text, ent)
    _read_office(text, ent)
    _read_course_code(text, ent)
    _read_term(text, ent)
    return ent
