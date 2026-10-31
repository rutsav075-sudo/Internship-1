"""Leakage-safe baseline comparison; not a substitute for real data validation."""

import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline

from app.ml import SEED, dataset

if __name__ == "__main__":
    x, y = dataset()
    reports = []
    for name, settings in [
        ("word_1_2", {"ngram_range": (1, 2), "stop_words": "english"}),
        ("char_3_5", {"analyzer": "char_wb", "ngram_range": (3, 5)}),
    ]:
        pipe = Pipeline(
            [
                ("features", TfidfVectorizer(sublinear_tf=True, **settings)),
                ("model", LogisticRegression(C=4, max_iter=1000, random_state=SEED)),
            ]
        )
        scores = cross_validate(
            pipe,
            x,
            y,
            cv=StratifiedKFold(3, shuffle=True, random_state=SEED),
            scoring=["accuracy", "f1_macro"],
        )
        reports.append(
            {
                "name": name,
                "accuracy_mean": float(scores["test_accuracy"].mean()),
                "macro_f1_mean": float(scores["test_f1_macro"].mean()),
                "macro_f1_std": float(scores["test_f1_macro"].std()),
            }
        )
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/experiments.json").write_text(json.dumps(reports, indent=2))
    print(json.dumps(reports, indent=2))
