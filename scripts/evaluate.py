"""Run from project root: python -m scripts.evaluate"""

import json
from pathlib import Path

from app.ml import evaluate

if __name__ == "__main__":
    report = evaluate()
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/evaluation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
