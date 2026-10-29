"""Sensitive-payload detection for free-text fields (FR-013).

Detects values that look like customer identifiers so they are not stored in requests,
comments or notifications. Rules are illustrative; the production rule set must be defined
with Information Security and Privacy.
"""
import re


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
        alt = not alt
    return total % 10 == 0


# Order matters: more specific patterns run first and their matches are masked before the next.
RULES = [
    ("NPWP", re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b"), None),
    ("Email address", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"), None),
    ("Phone number", re.compile(r"(?<!\d)(?:\+62|62|0)8\d{7,11}(?!\d)"), None),
    ("Card number", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
     lambda m: _luhn(re.sub(r"\D", "", m))),
    ("NIK (national ID)", re.compile(r"(?<!\d)\d{16}(?!\d)"), None),
    ("Account / CIF number", re.compile(r"(?<!\d)\d{10,15}(?!\d)"), None),
]


def _mask(value: str) -> str:
    raw = re.sub(r"\s", "", value)
    return raw[:2] + "•" * max(len(raw) - 4, 2) + raw[-2:]


def scan(text: str) -> list[dict]:
    findings, working = [], text or ""
    for label, pattern, check in RULES:
        for m in list(pattern.finditer(working)):
            if check and not check(m.group()):
                continue
            findings.append({"type": label, "sample": _mask(m.group())})
        working = pattern.sub(lambda m: "#" * len(m.group()) if not check or check(m.group()) else m.group(), working)
    return findings


def redact(text: str) -> str:
    out = text or ""
    for label, pattern, check in RULES:
        tag = "[REDACTED-" + label.split(" ")[0].upper().strip("/") + "]"
        out = pattern.sub(lambda m: tag if not check or check(m.group()) else m.group(), out)
    return out
