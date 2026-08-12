#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


VALID_SUBJECTS = {"cs.SE"}

REQUIRED_FIELDS = ("LinkedIn", "Paper", "Subject", "EndorsementCode")
ENDORSEMENT_CODE_RE = re.compile(r"^[A-Za-z0-9]{6}$")


def validate_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_linkedin(value: str) -> bool:
    if not validate_https_url(value):
        return False
    parsed = urlparse(value)
    if parsed.netloc not in {"www.linkedin.com", "linkedin.com"}:
        return False
    return parsed.path.startswith("/in/") or parsed.path.startswith("/pub/")


def parse_request_file(path: Path) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    if len(lines) != len(REQUIRED_FIELDS):
        errors.append(
            f"must contain exactly {len(REQUIRED_FIELDS)} non-empty lines in the documented format"
        )

    fields: dict[str, str] = {}
    seen_names: list[str] = []

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(f"line {index}: must not be blank")
            continue
        if ":" not in line:
            errors.append(f"line {index}: expected 'Field: value'")
            continue

        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        seen_names.append(name)

        if name not in REQUIRED_FIELDS:
            errors.append(f"line {index}: unknown field '{name}'")
            continue
        if name in fields:
            errors.append(f"line {index}: duplicate field '{name}'")
            continue
        if not value:
            errors.append(f"line {index}: field '{name}' must not be empty")
            continue

        fields[name] = value

    if seen_names and tuple(seen_names) != REQUIRED_FIELDS:
        errors.append(
            "fields must appear exactly once and in this order: LinkedIn, Paper, Subject, EndorsementCode"
        )

    for field in REQUIRED_FIELDS:
        if field not in fields:
            errors.append(f"missing field '{field}'")

    linkedin = fields.get("LinkedIn")
    if linkedin and not validate_linkedin(linkedin):
        errors.append(
            "LinkedIn must be an https://www.linkedin.com/in/... or https://www.linkedin.com/pub/... URL"
        )

    paper = fields.get("Paper")
    if paper and not validate_https_url(paper):
        errors.append("Paper must be a public https:// URL")

    subject = fields.get("Subject")
    if subject and subject not in VALID_SUBJECTS:
        errors.append("Subject must be cs.SE — I only endorse for cs.SE")

    endorsement_code = fields.get("EndorsementCode")
    if endorsement_code and not ENDORSEMENT_CODE_RE.fullmatch(endorsement_code):
        errors.append("EndorsementCode must be a six-character alphanumeric code")

    return errors


def iter_request_files(paths: list[str]) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    return sorted(Path("requests").glob("*.txt"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate endorsement request files under requests/."
    )
    parser.add_argument("paths", nargs="*", help="Specific request files to validate.")
    args = parser.parse_args()

    paths = iter_request_files(args.paths)
    if not paths:
        print("No request files found.", file=sys.stderr)
        return 1

    has_errors = False
    for path in paths:
        errors = parse_request_file(path)
        if not errors:
            print(f"OK: {path}")
            continue

        has_errors = True
        print(f"ERROR: {path}")
        for error in errors:
            print(f"  - {error}")

    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
