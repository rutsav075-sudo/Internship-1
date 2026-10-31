"""Create a local .env without printing any secrets. Never overwrites existing credentials."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    env = ROOT / ".env"
    if env.exists():
        print("Existing .env left unchanged. Edit it locally to configure Gemini.")
    else:
        env.write_text(
            f"GEMINI_API_KEY=\nGEMINI_MODEL=gemini-3.1-flash-lite\nADMIN_TOKEN={secrets.token_urlsafe(32)}\n"
        )
        env.chmod(0o600)
        print(
            "Created .env with a random admin token. Open the file locally to configure Gemini and copy your admin token."
        )
