"""Learning layer: feedback sentiment model (Naive Bayes).

Proposal section 10 compares Naive Bayes against logistic regression for the
short feedback comments and starts with Naive Bayes as the baseline - a few
hundred short comments is exactly the size where it holds up.

The model does one job: tell whether a comment was positive, neutral or
negative, so a negative comment can push the conversation towards a hand-off
and so staff can see the sentiment trend on the dashboard.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from code.nlu import normalize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"

MODEL_PATH = MODELS / "sentiment_model.joblib"
METRICS_PATH = MODELS / "sentiment_metrics.json"
CORPUS_FILE = "feedback_corpus.csv"

RANDOM_SEED = 42


@dataclass
class SentimentPrediction:
    sentiment: str
    confidence: float


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("counts", CountVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1)),
            ("clf", MultinomialNB(alpha=0.3)),
        ]
    )


def load_corpus() -> list[dict]:
    import csv

    path = DATA / CORPUS_FILE
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            text = (row.get("text") or "").strip()
            label = (row.get("sentiment") or "").strip()
            if text and label:
                rows.append({"text": text, "sentiment": label})
    return rows


def train(force: bool = False) -> dict:
    rows = load_corpus()
    if len(rows) < 30:
        raise RuntimeError("feedback corpus too small - expected at least 30 comments")

    texts = [normalize(r["text"]) for r in rows]
    labels = [r["sentiment"] for r in rows]

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=RANDOM_SEED, stratify=labels
    )
    model = build_pipeline()
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    fold_scores = []
    for train_idx, test_idx in cv.split(texts, labels):
        fold = build_pipeline()
        fold.fit([texts[i] for i in train_idx], [labels[i] for i in train_idx])
        fold_pred = fold.predict([texts[i] for i in test_idx])
        fold_scores.append(f1_score([labels[i] for i in test_idx], fold_pred, average="macro", zero_division=0))

    MODELS.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metrics = {
        "corpus_size": len(rows),
        "holdout_accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "holdout_macro_f1": round(float(f1_score(y_test, predicted, average="macro", zero_division=0)), 4),
        "cv5_macro_f1_mean": round(float(sum(fold_scores) / len(fold_scores)), 4),
        "seed": RANDOM_SEED,
        "caveat": (
            "All comments in the corpus were drafted by the same source, so the "
            "numbers measure how well the model fits that writer - not how well it "
            "reads a real student comment."
        ),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


class SentimentModel:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline

    @classmethod
    def load(cls) -> "SentimentModel":
        if not MODEL_PATH.exists():
            train(force=True)
        return cls(joblib.load(MOD_PATH))

    def predict(self, text: str) -> SentimentPrediction:
        probabilities = self.pipeline.predict_proba([normalize(text)])[0]
        classes = list(self.pipeline.named_steps["clf"].classes_)
        best = max(range(len(classes)), key=lambda i: probabilities[i])
        return SentimentPrediction(
            sentiment=classes[best], confidence=round(float(probabilities[best]), 4)
        )


_MODEL: SentimentModel | None = None


def get_model() -> SentimentModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentimentModel.load()
    return _MODEL
