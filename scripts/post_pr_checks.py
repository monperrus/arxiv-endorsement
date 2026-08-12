#!/usr/bin/env python3
"""Run check-paper.py against each valid endorsement request PR and post the result as a PR comment.

A request PR is "valid" when its requests/*.txt file passes scripts/validate_request_files.py.
Skips PRs that already carry a check comment (idempotent).

Usage:
  ./scripts/post_pr_checks.py [--repo owner/repo] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "monperrus/arxiv-endorsement"
COMMENT_MARKER = "<!-- arxiv-endorsement-check -->"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_paper = load_module(ROOT / "check-paper.py", "check_paper")
validate_request_files = load_module(ROOT / "scripts" / "validate_request_files.py", "validate_request_files")


def gh_json(*args: str):
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def list_open_prs(repo: str) -> list[dict]:
    return gh_json(
        "pr", "list", "--repo", repo, "--state", "open",
        "--json", "number,url,files,headRefOid",
    )


def fetch_file_content(repo: str, path: str, ref: str) -> str:
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}", "--jq", ".content"],
        capture_output=True, text=True, check=True,
    )
    return base64.b64decode(proc.stdout.strip()).decode("utf-8")


def already_commented(repo: str, pr_number: int) -> bool:
    comments = gh_json("pr", "view", str(pr_number), "--repo", repo, "--json", "comments")["comments"]
    return any(COMMENT_MARKER in c.get("body", "") for c in comments)


def parse_fields(text: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        name, value = line.split(":", 1)
        fields[name.strip()] = value.strip()
    return fields


def build_comment(result: dict, paper_url: str) -> str:
    gates = [
        ("gate1_is_scientific_paper", "Gate 1 — Scientific paper"),
        ("gate2_is_software_engineering", "Gate 2 — Software engineering topic"),
        ("gate3_passes_arxiv_quality", "Gate 3 — arXiv quality standards"),
    ]

    def verdict_md(v: bool) -> str:
        return "✓ PASS" if v else "✗ FAIL"

    def conf_md(c: str) -> str:
        return {"high": "", "medium": " *(medium confidence)*", "low": " *(low confidence)*"}.get(c, "")

    overall = result.get("overall_verdict", all(result[k]["verdict"] for k, _ in gates))
    overall_str = "✓ SUITABLE for arXiv cs.SE endorsement" if overall else "✗ NOT suitable for arXiv cs.SE endorsement"

    lines = [
        COMMENT_MARKER,
        "## arXiv SE endorsement check (automated)",
        "",
        f"Paper: {paper_url}",
        f"Model: {check_paper.MODEL}",
        "",
        f"**Overall: {overall_str}**",
        "",
    ]
    for key, label in gates:
        g = result[key]
        lines.append(f"- {verdict_md(g['verdict'])} {label}{conf_md(g['confidence'])}")
        if not g["verdict"] and g.get("feedback"):
            lines.append(f"  - {g['feedback']}")
    lines += ["", result.get("summary", "")]
    return "\n".join(lines)


def post_comment(repo: str, pr_number: int, body: str, edit_last: bool = False) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
        body_path = f.name
    try:
        args = ["gh", "pr", "comment", str(pr_number), "--repo", repo, "--body-file", body_path]
        if edit_last:
            args += ["--edit-last", "--create-if-none"]
        subprocess.run(args, check=True)
    finally:
        Path(body_path).unlink(missing_ok=True)


def process_pr(repo: str, pr: dict, dry_run: bool, update: bool) -> None:
    number = pr["number"]
    txt_files = [f["path"] for f in pr["files"] if f["path"].startswith("requests/") and f["path"].endswith(".txt")]
    if not txt_files:
        return

    was_commented = already_commented(repo, number)
    if was_commented and not update:
        print(f"PR #{number}: already checked, skipping", file=sys.stderr)
        return

    content = fetch_file_content(repo, txt_files[0], pr["headRefOid"])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(content)
        request_path = Path(f.name)
    try:
        errors = validate_request_files.parse_request_file(request_path)
    finally:
        request_path.unlink(missing_ok=True)

    if errors:
        print(f"PR #{number}: invalid request, skipping ({'; '.join(errors)})", file=sys.stderr)
        return

    fields = parse_fields(content)
    paper_url = fields["Paper"]
    print(f"PR #{number}: checking {paper_url} …", file=sys.stderr)

    try:
        tmp_pdf = check_paper.download_pdf(paper_url)
    except Exception as e:
        print(f"PR #{number}: failed to download paper: {e}", file=sys.stderr)
        return

    try:
        text = check_paper.pdf_to_text(str(tmp_pdf))
        result = check_paper.evaluate_paper(text)
    except Exception as e:
        print(f"PR #{number}: evaluation failed: {e}", file=sys.stderr)
        return
    finally:
        tmp_pdf.unlink(missing_ok=True)

    comment = build_comment(result, paper_url)
    if dry_run:
        print(f"\n--- PR #{number} (dry run, not posted) ---\n{comment}\n")
    else:
        post_comment(repo, number, comment, edit_last=was_commented)
        print(f"PR #{number}: comment {'updated' if was_commented else 'posted'}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--dry-run", action="store_true", help="print comments instead of posting them")
    parser.add_argument("--update", action="store_true", help="re-run and edit the existing check comment on already-checked PRs")
    args = parser.parse_args()

    for pr in list_open_prs(args.repo):
        process_pr(args.repo, pr, args.dry_run, args.update)


if __name__ == "__main__":
    main()
