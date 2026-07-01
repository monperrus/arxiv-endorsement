#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse


VALID_SUBJECTS = {
    "astro-ph.CO",
    "astro-ph.EP",
    "astro-ph.GA",
    "astro-ph.HE",
    "astro-ph.IM",
    "astro-ph.SR",
    "cond-mat.dis-nn",
    "cond-mat.mes-hall",
    "cond-mat.mtrl-sci",
    "cond-mat.other",
    "cond-mat.quant-gas",
    "cond-mat.soft",
    "cond-mat.stat-mech",
    "cond-mat.str-el",
    "cond-mat.supr-con",
    "cs.AI",
    "cs.AR",
    "cs.CC",
    "cs.CE",
    "cs.CG",
    "cs.CL",
    "cs.CR",
    "cs.CV",
    "cs.CY",
    "cs.DB",
    "cs.DC",
    "cs.DL",
    "cs.DM",
    "cs.DS",
    "cs.ET",
    "cs.FL",
    "cs.GL",
    "cs.GR",
    "cs.GT",
    "cs.HC",
    "cs.IR",
    "cs.IT",
    "cs.LG",
    "cs.LO",
    "cs.MA",
    "cs.MM",
    "cs.MS",
    "cs.NA",
    "cs.NE",
    "cs.NI",
    "cs.OH",
    "cs.OS",
    "cs.PF",
    "cs.PL",
    "cs.RO",
    "cs.SC",
    "cs.SD",
    "cs.SE",
    "cs.SI",
    "cs.SY",
    "econ.EM",
    "econ.GN",
    "econ.TH",
    "eess.AS",
    "eess.IV",
    "eess.SP",
    "eess.SY",
    "math.AC",
    "math.AG",
    "math.AP",
    "math.AT",
    "math.CA",
    "math.CO",
    "math.CT",
    "math.CV",
    "math.DG",
    "math.DS",
    "math.FA",
    "math.GM",
    "math.GN",
    "math.GR",
    "math.GT",
    "math.HO",
    "math.IT",
    "math.KT",
    "math.LO",
    "math.MG",
    "math.MP",
    "math.NA",
    "math.NT",
    "math.OA",
    "math.OC",
    "math.PR",
    "math.QA",
    "math.RA",
    "math.RT",
    "math.SG",
    "math.SP",
    "math.ST",
    "nlin.AO",
    "nlin.CD",
    "nlin.CG",
    "nlin.PS",
    "nlin.SI",
    "physics.acc-ph",
    "physics.ao-ph",
    "physics.app-ph",
    "physics.atm-clus",
    "physics.atom-ph",
    "physics.bio-ph",
    "physics.chem-ph",
    "physics.class-ph",
    "physics.comp-ph",
    "physics.data-an",
    "physics.ed-ph",
    "physics.flu-dyn",
    "physics.gen-ph",
    "physics.geo-ph",
    "physics.hist-ph",
    "physics.ins-det",
    "physics.med-ph",
    "physics.optics",
    "physics.plasm-ph",
    "physics.pop-ph",
    "physics.soc-ph",
    "physics.space-ph",
    "q-bio.BM",
    "q-bio.CB",
    "q-bio.GN",
    "q-bio.MN",
    "q-bio.NC",
    "q-bio.OT",
    "q-bio.PE",
    "q-bio.QM",
    "q-bio.SC",
    "q-bio.TO",
    "q-fin.CP",
    "q-fin.EC",
    "q-fin.GN",
    "q-fin.MF",
    "q-fin.PM",
    "q-fin.PR",
    "q-fin.RM",
    "q-fin.ST",
    "q-fin.TR",
    "stat.AP",
    "stat.CO",
    "stat.ME",
    "stat.ML",
    "stat.OT",
    "stat.TH",
}

REQUIRED_FIELDS = ("LinkedIn", "Paper", "Subject")


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
            "fields must appear exactly once and in this order: LinkedIn, Paper, Subject"
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
        errors.append(
            "Subject must be a valid arXiv category ID from https://arxiv.org/category_taxonomy"
        )

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
