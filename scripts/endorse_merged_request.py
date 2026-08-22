#!/usr/bin/env python3
"""Register an approved, merged endorsement request with arXiv.

Credentials are intentionally read only from the ARXIV_USERNAME and
ARXIV_PASSWORD environment variables.  The arXiv endpoints used here mirror
the browser flow recorded in the repository HAR capture.
"""

from __future__ import annotations

import argparse
import os
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from validate_request_files import REQUIRED_FIELDS, parse_request_file


LOGIN_URL = "https://arxiv.org/login?next_page=https%3A//arxiv.org/user"
ENDORSE_URL = "https://arxiv.org/auth/endorse"
USER_AGENT = "arxiv-endorsement-github-action/1.0"


class EndorsementFormParser(HTMLParser):
    """Extract the confirmation form's hidden endorsement code."""

    def __init__(self) -> None:
        super().__init__()
        self.code: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        attributes = dict(attrs)
        if attributes.get("name") == "x" and attributes.get("type") == "hidden":
            self.code = attributes.get("value")


def read_fields(path: Path) -> dict[str, str]:
    errors = parse_request_file(path)
    if errors:
        raise ValueError("; ".join(errors))

    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, value = line.split(":", 1)
        fields[name.strip()] = value.strip()
    if tuple(fields) != REQUIRED_FIELDS:
        raise ValueError("request fields are not in the required order")
    return fields


def request(opener, url: str, data: dict[str, str] | None = None) -> str:
    encoded_data = urlencode(data).encode("utf-8") if data is not None else None
    http_request = Request(url, data=encoded_data, headers={"User-Agent": USER_AGENT})
    with opener.open(http_request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Endorse one merged arXiv request.")
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args()

    username = os.environ.get("ARXIV_USERNAME")
    password = os.environ.get("ARXIV_PASSWORD")
    if not username or not password:
        print("ARXIV_USERNAME and ARXIV_PASSWORD must be configured as repository secrets.", file=sys.stderr)
        return 2

    try:
        fields = read_fields(args.request_file)
        code = fields["EndorsementCode"]
        opener = build_opener(HTTPCookieProcessor(CookieJar()))

        # This endpoint returns a redirect to /user for a successful login.
        request(opener, LOGIN_URL, {"username": username, "password": password})
        confirmation_page = request(
            opener,
            f"https://arxiv.org/auth/endorse.php?{urlencode({'x': code, 'submit': 'Submit'})}",
        )

        form = EndorsementFormParser()
        form.feed(confirmation_page)
        if form.code != code:
            raise RuntimeError("arXiv did not return a confirmation form for this endorsement code")
        if "cs.SE (Software Engineering)" not in confirmation_page:
            raise RuntimeError("arXiv confirmation page does not match the allowed cs.SE subject")

        result_page = request(
            opener,
            ENDORSE_URL,
            {
                "x": code,
                "choice": "1",
                "seen_paper": "on",
                "comment": "Endorsed after the repository's documented review protocol.",
                "submit": "Submit",
            },
        )
        if "Thank you for endorsing" not in result_page:
            raise RuntimeError("arXiv did not confirm the endorsement")
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as error:
        print(f"Endorsement was not registered: {error}", file=sys.stderr)
        return 1

    print(f"Registered arXiv endorsement code from {args.request_file}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
