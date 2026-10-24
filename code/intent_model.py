"""Learning layer: the intent model (TF-IDF + logistic regression).

Proposal section 10 compares TF-IDF + logistic regression against a cloud NLU
service and picks the local model: the data stays on the laptop, the predicted
probability doubles as the confidence score, and every prediction can be
explained by its top words.

The model is trained from the labelled corpus in data/ plus any query the
staff labelled in the dashboard, which is the "adaptive" loop of proposal
section 5: a missed question becomes training data on the next retrain.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline

from code.nlu import normalize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"

MODEL_PATH = MODELS / "intent_model.joblib"
METRICS_PATH = MODELS / "intent_metrics.json"

# Every labelled source the project has, merged into one training set. Order
# is trust order: the team's own writing wins a duplicate, then the AI drafts,
# then what staff labelled in the dashboard, then questions harvested from the
# chat log (real questions a student actually typed and the assistant answered).
CORPUS_FILES = [
    ("starter_corpus_50.csv", "team-written"),
    ("intent_corpus_augmented.csv", "AI-drafted"),
    ("staff_labeled_queries.csv", "staff-labelled"),
    ("harvested_chat_queries.csv", "harvested"),
]

RANDOM_SEED = 42
TEST_SIZE = 0.20

STAFF_LABEL_PATH = DATA / "staff_labeled_queries.csv"


@dataclass
class IntentPrediction:
    intent: str
    confidence: float
    alternatives: list[tuple[str, float]]
    top_terms: list[str]


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    min_df=1,
                    strip_accents="unicode",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=2.0,
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def load_corpus() -> list[dict]:
    """Every labelled row from data/, de-duplicated on the normalized text.

    The first occurrence wins, so the team's own wording is kept when the
    augmented file repeats it.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for filename, origin in CORPUS_FILES:
        path = DATA / filename
        if not path.exists():
            continue
        import csv

        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                text = (row.get("text") or "").strip()
                intent = (row.get("intent") or "").strip()
                if not text or not intent:
                    continue
                key = normalize(text)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "text": text,
                        "intent": intent,
                        "origin": origin,
                        "source": row.get("source", ""),
                    }
                )
    return rows


def _split(rows: list[dict]) -> tuple[list[str], list[str], list[str], list[str]]:
    texts = [normalize(r["text"]) for r in rows]
    labels = [r["intent"] for r in rows]
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=labels
    )
    return x_train, x_test, y_train, y_test


def evaluate(rows: list[dict]) -> dict:
    """Hold-out split plus 5-fold cross-validation over the whole corpus."""
    x_train, x_test, y_train, y_test = _split(rows)
    model = build_pipeline()
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)

    labels = sorted(set(y_train))
    report = f1_score(y_test, predicted, average="macro", labels=labels, zero_division=0)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    fold_scores = []
    for train_idx, test_idx in cv.split([normalize(r["text"]) for r in rows], [r["intent"] for r in rows]):
        fold_model = build_pipeline()
        fold_model.fit(
            [normalize(rows[i]["text"]) for i in train_idx], [rows[i]["intent"] for i in train_idx]
        )
        fold_pred = fold_model.predict([normalize(rows[i]["text"]) for i in test_idx])
        fold_scores.append(
            f1_score(
                [rows[i]["intent"] for i in test_idx],
                fold_pred,
                average="macro",
                zero_division=0,
            )
        )

    per_class = {}
    for label in labels:
        true_pos = sum(1 for t, p in zip(y_test, predicted) if t == label and p == label)
        support = sum(1 for t in y_test if t == label)
        per_class[label] = {
            "support": support,
            "recall": round(true_pos / support, 4) if support else None,
        }

    return {
        "corpus_size": len(rows),
        "intents": len(labels),
        "holdout_accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "holdout_macro_f1": round(float(report), 4),
        "cv5_macro_f1_mean": round(float(np.mean(fold_scores)), 4),
        "cv5_macro_f1_std": round(float(np.std(fold_scores)), 4),
        "cv5_fold_scores": [round(float(s), 4) for s in fold_scores],
        "per_class_recall": per_class,
        "confusion_matrix": confusion_matrix(y_test, predicted, labels=labels).tolist(),
        "confusion_labels": labels,
        "seed": RANDOM_SEED,
        "test_size": TEST_SIZE,
        "caveat": (
            "The hold-out split is drawn from the same writer distribution as the "
            "training data, so these numbers are optimistic. The proposal's target "
            "is macro F1 >= 0.80 on 50 questions written by a member who did not "
            "write the training phrases - that set does not exist yet."
        ),
    }


def add_staff_label(text: str, intent: str) -> None:
    """Add one staff-labelled question to the training set.

    This is the adaptive loop of proposal section 5: a question the assistant
    could not answer becomes training data at the next retrain.
    """
    import csv
    from datetime import date

    row = {
        "text": (text or "").strip(),
        "intent": (intent or "").strip(),
        "source": "staff-labelled in the dashboard",
        "date": date.today().isoformat(),
    }
    new_file = not STAFF_LABEL_PATH.exists()
    with STAFF_LABEL_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "intent", "source", "date"])
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def retrain() -> dict:
    """Retrain on everything in data/ and swap the in-memory model."""
    global _MODEL
    metrics = train(force=True)
    _MODEL = None
    get_model()
    return metrics


def train(force: bool = False) -> dict:
    """Fit the model, save it and save the metrics next to it."""
    rows = load_corpus()
    if len(rows) < 20:
        raise RuntimeError("corpus too small to train - run scripts/prepare_corpus.py first")
    if MODEL_PATH.exists() and not force:
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    model = build_pipeline()
    model.fit([normalize(r["text"]) for r in rows], [r["intent"] for r in rows])

    MODELS.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metrics = evaluate(rows)
    metrics["trained_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    metrics["model_path"] = str(MODEL_PATH.relative_to(ROOT))
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


class IntentModel:
    """Thin wrapper that adds confidence and alternatives to the pipeline."""

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline

    @classmethod
    def load(cls) -> "IntentModel":
        if not MODEL_PATH.exists():
            train(force=True)
        return cls(joblib.load(MODEL_PATH))

    def predict(self, text: str) -> IntentPrediction:
        vector = self.pipeline.named_steps["tfidf"]
        classifier = self.pipeline.named_steps["clf"]
        features = vector.transform([normalize(text)])
        probabilities = classifier.predict_proba(features)[0]
        classes = list(classifier.classes_)

        ranked = sorted(zip(classes, probabilities), key=lambda pair: pair[1], reverse=True)
        best_intent, best_prob = ranked[0]

        names = np.array(vector.get_feature_names_out())
        weights = classifier.coef_[list(classifier.classes_).index(best_intent)]
        top = names[np.argsort(weights)[-6:][::-1]]

        return IntentPrediction(
            intent=best_intent,
            confidence=round(float(best_prob), 4),
            alternatives=[(name, round(float(prob), 4)) for name, prob in ranked[1:4]],
            top_terms=[str(term) for term in top],
        )


_MODEL: IntentModel | None = None


def get_model() -> IntentModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = IntentModel.load()
    return _MODEL
