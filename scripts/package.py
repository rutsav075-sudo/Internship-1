"""Build a source archive while explicitly excluding credentials, databases and caches."""

import argparse
import zipfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "edxso-ai-v1.2.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    secrets = [
        v for k, v in dotenv_values(ROOT / ".env").items() if k in {"GEMINI_API_KEY", "ADMIN_TOKEN"} and v
    ]
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == output:
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if (
            path.name in {".env", ".coverage", ".git-credentials", ".netrc"}
            or (path.name.startswith(".env.") and path.name != ".env.example")
            or path.suffix in {".pem", ".key"}
            or ".sqlite3" in path.name
            or path.suffix == ".db"
            or ".db-" in path.name
            or path.suffix in {".pyc", ".log", ".zip"}
        ):
            continue
        if relative.parts[0] == "artifacts" and path.suffix not in {".json", ".txt"}:
            continue
        payload = path.read_bytes()
        if any(secret.encode() in payload for secret in secrets):
            raise SystemExit(f"Refusing to package credential-containing file: {relative}")
        files.append(path)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, Path("edxso-ai") / path.relative_to(ROOT))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise SystemExit("Archive integrity check failed")
    print(
        f"Packaged {len(files)} files. Credentials/databases excluded; archive integrity and secret checks passed."
    )


if __name__ == "__main__":
    main()
