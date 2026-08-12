#!/usr/bin/env python3
"""Download a file from a Zenodo record.

Usage:
  ./download_zenodo.py <zenodo-url> [-o OUTPUT] [--match PATTERN]

Accepts either a direct file URL
  (https://zenodo.org/records/<id>/files/<name>)
or a record page / API URL
  (https://zenodo.org/records/<id>), in which case the first file is picked
  (or the first whose name contains --match, if given).

Uses curl_cffi with browser TLS impersonation: Zenodo's WAF blocks plain
urllib/curl requests ("unusual traffic") based on TLS fingerprint, not IP
or User-Agent header alone. The record/DOI HTML pages additionally sit
behind a JS cookie challenge that curl_cffi can't clear either, so this
module always resolves through the /api/records/<id> JSON endpoint, which
is not challenge-protected.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
from pathlib import Path

try:
    from curl_cffi import requests
except ImportError:
    sys.exit("pip install curl_cffi")

IMPERSONATE = "chrome"


def resolve_file_url(url: str, match: str | None) -> str:
    """Resolve a Zenodo record/DOI/file URL to a direct file download URL."""
    if re.search(r"/records?/\d+/files/", url):
        return url

    # HTML pages (/records/<id>, /doi/10.5281/zenodo.<id>) are behind a
    # JS cookie challenge that a plain client can't pass; the /api/records/<id>
    # endpoint used below is not, so pull the numeric id straight out of the URL.
    record_match = re.match(r"https?://zenodo\.org/records?/(\d+)", url) or re.match(
        r"https?://zenodo\.org/doi/10\.5281/zenodo\.(\d+)", url
    )
    if not record_match:
        return url  # assume it's already a direct file URL

    record_id = record_match.group(1)
    resp = requests.get(f"https://zenodo.org/api/records/{record_id}", impersonate=IMPERSONATE, timeout=30)
    resp.raise_for_status()
    files = resp.json().get("files", [])
    if not files:
        sys.exit(f"No files found in Zenodo record {record_id}")

    if match:
        files = [f for f in files if match in f.get("key", "")]
        if not files:
            sys.exit(f"No file matching {match!r} in Zenodo record {record_id}")
    else:
        pdfs = [f for f in files if f.get("key", "").lower().endswith(".pdf")]
        if pdfs:
            files = pdfs

    return files[0]["links"]["self"]


def download(file_url: str, output: Path) -> Path:
    resp = requests.get(file_url, impersonate=IMPERSONATE, timeout=120)
    resp.raise_for_status()

    if output.is_dir():
        filename = Path(urllib.parse.urlparse(file_url).path).name
        output = output / filename

    output.write_bytes(resp.content)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a file from a Zenodo record")
    parser.add_argument("url", help="Zenodo record or direct file URL")
    parser.add_argument("-o", "--output", type=Path, default=Path("."), help="output file or directory (default: .)")
    parser.add_argument("--match", help="substring to select a file when the record has several")
    args = parser.parse_args()

    file_url = resolve_file_url(args.url, args.match)
    if file_url != args.url:
        print(f"Resolved to: {file_url}", file=sys.stderr)

    path = download(file_url, args.output)
    print(path)


if __name__ == "__main__":
    main()
