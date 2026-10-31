"""Best-effort contact-data redaction and spreadsheet-safe export helpers.

Not a comprehensive personal-data detection or compliance solution.
"""

import re

EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)")


def redact(text: str) -> str:
    return PHONE.sub("[number removed]", EMAIL.sub("[email removed]", text))


def spreadsheet_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
