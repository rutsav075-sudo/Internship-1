"""Reproducible intent classification and lexical knowledge retrieval."""

import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .schemas import FAQ

ROOT = Path(__file__).resolve().parents[1]
SEED = 42


LABELS = {"Admissions", "Fees", "Academics", "Transport", "Support"}


def read_examples(filename: str) -> tuple[list[str], list[str]]:
    raw = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != LABELS:
        raise ValueError("Training data must contain exactly the five supported intent classes")
    rows = []
    seen = set()
    for label, texts in raw.items():
        if not isinstance(texts, list) or len(texts) < 4:
            raise ValueError("Each intent needs at least four labelled examples")
        for text in texts:
            if not isinstance(text, str) or len(text.strip()) < 2 or text.strip().casefold() in seen:
                raise ValueError("Training examples must be nonempty, unique strings")
            seen.add(text.strip().casefold())
            rows.append((text.strip(), label))
    return [r[0] for r in rows], [r[1] for r in rows]


def dataset(*, augmented: bool = True) -> tuple[list[str], list[str]]:
    x, y = read_examples("training.json")
    if augmented:
        extra_x, extra_y = read_examples("augmentation.json")
        if set(t.casefold() for t in x) & set(t.casefold() for t in extra_x):
            raise ValueError("Augmentation must not duplicate the original evaluation examples")
        x += extra_x
        y += extra_y
    return x, y


def dataset_fingerprint() -> str:
    payload = json.dumps(dataset(), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def pipeline():
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")),
            ("classifier", LogisticRegression(C=4, max_iter=1000, random_state=SEED)),
        ]
    )


class Models:
    def __init__(self):
        x, y = dataset()
        self.classifier = pipeline().fit(x, y)
        self.faqs = [
            FAQ.model_validate(row).model_dump() for row in json.loads((ROOT / "data/faqs.json").read_text())
        ]
        if not self.faqs or len({r["id"] for r in self.faqs}) != len(self.faqs):
            raise ValueError("Knowledge base must be nonempty and have unique IDs")
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.matrix = self.vectorizer.fit_transform([f"{f['question']} {f['keywords']}" for f in self.faqs])

    def classify(self, text):
        probs = self.classifier.predict_proba([text])[0]
        i = int(np.argmax(probs))
        # An illustrative model score, not a calibrated probability of correctness.
        return str(self.classifier.classes_[i]), round(float(probs[i]), 4)

    def retrieve(self, text, limit=3):
        scores = cosine_similarity(self.vectorizer.transform([text]), self.matrix)[0]
        return [
            {**self.faqs[i], "score": round(max(0.0, min(1.0, float(scores[i]))), 4)}
            for i in np.argsort(-scores)[:limit]
            if scores[i] >= 0.09
        ]


def evaluate():
    x, y = dataset(augmented=False)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.25, random_state=SEED, stratify=y)
    extra_x, extra_y = read_examples("augmentation.json")
    # Preserve the original 15-example test partition; augmentation affects training only.
    x_train += extra_x
    y_train += extra_y
    model = pipeline().fit(x_train, y_train)
    pred = model.predict(x_test)
    labels = sorted(set(y))
    return {
        "accuracy": round(accuracy_score(y_test, pred), 4),
        "macro_f1": round(f1_score(y_test, pred, average="macro"), 4),
        "train_samples": len(x_train),
        "test_samples": len(x_test),
        "seed": SEED,
        "serving_samples": len(dataset()[0]),
        "dataset_sha256": dataset_fingerprint(),
        "feature_description": "Word TF–IDF, unigrams/bigrams, English stop words, sublinear term frequency",
        "labels": labels,
        "confusion_matrix": confusion_matrix(y_test, pred, labels=labels).tolist(),
        "report": classification_report(y_test, pred, output_dict=True, zero_division=0),
        "caveat": "Synthetic English data only: 60 original examples plus 75 augmentation examples. The original 15 test examples stay fixed; the evaluation model fits the remaining 45 plus augmentation. Serving fits all 135. This is not production validation.",
    }
