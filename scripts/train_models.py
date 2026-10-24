"""Train the intent and sentiment models and print the metrics.

    python scripts/train_models.py

The metrics written to models/*.json are what the staff dashboard shows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code import intent_model, sentiment


def main() -> None:
    print("=" * 60)
    print("INTENT MODEL  (TF-IDF + logistic regression)")
    print("=" * 60)
    intent_metrics = intent_model.train(force=True)
    print(json.dumps(intent_metrics, indent=2))

    print()
    print("=" * 60)
    print("SENTIMENT MODEL  (Multinomial Naive Bayes)")
    print("=" * 60)
    sentiment_metrics = sentiment.train(force=True)
    print(json.dumps(sentiment_metrics, indent=2))

    print()
    print("Models written to models/ - start the app with:")
    print("    python -m streamlit run app.py")


if __name__ == "__main__":
    main()
