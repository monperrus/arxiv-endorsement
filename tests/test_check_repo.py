"""Tests for the deterministic parts of gate 4 (no network, no LLM)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_repo = _load(ROOT / "scripts" / "check_repo.py", "check_repo")


def matches(value: str, haystack: str) -> bool:
    return any(p.search(haystack) for p in check_repo.value_patterns(value))


@pytest.mark.parametrize(
    "value,text",
    [
        ("87.3", "accuracy,87.3\n"),
        ("87.3", "accuracy,87.312904\n"),  # the paper rounds, the data file does not
        ("87.3", "accuracy,0.873421\n"),  # reported as a percentage, stored as a fraction
        ("1,204", "n_samples = 1204"),
        ("42", "bugs: 42.0"),
        ("0.031", "p_value: 0.0312"),
    ],
)
def test_value_found(value, text):
    assert matches(value, text)


@pytest.mark.parametrize(
    "value,text",
    [
        ("87.3", "accuracy,187.3\n"),  # must not match a longer number to the left
        ("42", "bugs: 421"),
        ("42", "bugs: 4.2"),
        ("12.5", "12.49"),
    ],
)
def test_value_not_found(value, text):
    assert not matches(value, text)


def test_non_numeric_value_yields_no_patterns():
    assert check_repo.value_patterns("several") == []
    assert check_repo.value_patterns("") == []


def test_normalize_repo_url():
    assert check_repo.normalize_repo_url("https://github.com/owner/repo") == "https://github.com/owner/repo"
    assert check_repo.normalize_repo_url("https://github.com/owner/repo.git") == "https://github.com/owner/repo"
    assert check_repo.normalize_repo_url("https://github.com/owner/repo/tree/main/x") == "https://github.com/owner/repo"
    with pytest.raises(ValueError):
        check_repo.normalize_repo_url("https://github.com/owner")


def test_classify():
    assert check_repo.classify(Path("results/data.csv")) == "data"
    assert check_repo.classify(Path("scripts/run.py")) == "script"
    assert check_repo.classify(Path("paper/main.tex")) == "paper_source"
    assert check_repo.classify(Path("logo.svg")) == "other"


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "accuracy.csv").write_text("tool,accuracy\nours,87.31\nbaseline,71.02\n")
    (tmp_path / "run.py").write_text("THRESHOLD = 0.5\nprint('running')\n")
    (tmp_path / "paper.tex").write_text("We reach an accuracy of 99.9\\%.\n")
    (tmp_path / "README.md").write_text("# Our tool\nRun `python run.py`.\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("87.3 71.0 99.9\n")
    return tmp_path


def test_scan_finds_values_and_ignores_git(fake_repo: Path):
    claims = [
        {"id": "C1", "value": "87.3"},
        {"id": "C2", "value": "99.9"},
        {"id": "C3", "value": "12345"},
    ]
    hits = check_repo.scan_repo_for_values(fake_repo, claims)
    assert [h["path"] for h in hits["C1"]] == ["results/accuracy.csv"]
    # only the paper source carries this one, which is not valid evidence
    assert [(h["path"], h["kind"]) for h in hits["C2"]] == [("paper.tex", "paper_source")]
    assert hits["C3"] == []


def test_scan_keeps_data_files_when_a_common_value_is_everywhere(tmp_path: Path):
    for i in range(check_repo.MAX_EVIDENCE_FILES + 2):
        (tmp_path / f"a_doc{i}.md").write_text("we ran 30 scenarios\n")
    (tmp_path / "b_run.py").write_text("N = 30\n")
    (tmp_path / "z_numbers.csv").write_text("name,value\nHeldOut,30\n")
    hits = check_repo.scan_repo_for_values(tmp_path, [{"id": "C1", "value": "30"}])["C1"]
    assert len(hits) == check_repo.MAX_EVIDENCE_FILES
    assert [h["path"] for h in hits[:2]] == ["z_numbers.csv", "b_run.py"]


def test_inventory(fake_repo: Path):
    inv = check_repo.build_inventory(fake_repo)
    paths = {f["path"] for f in inv["files"]}
    assert "results/accuracy.csv" in paths
    assert not any(p.startswith(".git/") for p in paths)
    assert inv["n_scripts"] == 1
    assert inv["n_data"] == 1
    assert inv["has_license"] is False
    assert "Our tool" in inv["readme"]
    assert any("accuracy.csv" in p for p in inv["previews"])


def test_traceability():
    claims = [{"status": "data_file"}, {"status": "script"}, {"status": "not_found"}]
    backed, total, ratio = check_repo.traceability(claims)
    assert (backed, total) == (2, 3)
    assert ratio == pytest.approx(2 / 3)
    assert check_repo.traceability([]) == (0, 0, 1.0)


def test_empty_completion_names_the_token_budget():
    response = {"choices": [{"finish_reason": "length", "message": {"content": ""}}], "usage": {"completion_tokens": 8192}}
    with pytest.raises(RuntimeError, match="raise MAX_TOKENS"):
        check_repo._parse_json_response(response)


def test_payloads_use_a_budget_above_the_thinking_trap():
    assert check_repo.build_claims_payload("x")["max_tokens"] == check_repo.MAX_TOKENS
    assert check_repo.MAX_TOKENS >= 16384


def test_check_repo_reports_unclonable_repository(monkeypatch):
    monkeypatch.setattr(check_repo, "clone_repo", lambda url, dest: (False, "repository not found"))
    result = check_repo.check_repo("https://github.com/owner/missing", "paper text", lambda payload: {})
    assert result["verdict"] is False
    assert result["repo_accessible"] is False
    assert "could not be cloned" in result["feedback"]


def test_check_repo_end_to_end_with_stubbed_llm(fake_repo: Path, monkeypatch):
    import shutil

    def fake_clone(url: str, dest: Path):
        shutil.copytree(fake_repo, dest, ignore=shutil.ignore_patterns(".git"))
        subprocess.run(["git", "init", "--quiet"], cwd=dest, check=True)
        subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "--quiet", "-m", "init"],
            cwd=dest, check=True,
        )
        return True, "cloned"

    monkeypatch.setattr(check_repo, "clone_repo", fake_clone)

    def fake_complete(payload: dict) -> dict:
        is_claims = "extract the empirical numbers" in payload["messages"][0]["content"]
        body = (
            {"claims": [{"id": "C1", "value": "87.3", "unit": "%", "claim": "accuracy of our tool", "location": "Table 1"},
                        {"id": "C2", "value": "12345", "unit": "", "claim": "number of subjects", "location": "Section 3"}]}
            if is_claims
            else {
                "repo_matches_paper": {"verdict": True, "confidence": "high", "feedback": ""},
                "claims": [
                    {"id": "C1", "status": "data_file", "evidence": ["results/accuracy.csv"], "note": "stored"},
                    {"id": "C2", "status": "not_found", "evidence": [], "note": "absent"},
                ],
                "feedback": "Commit the subject list.",
                "summary": "Partially reproducible.",
            }
        )
        import json as _json
        return {"choices": [{"message": {"content": _json.dumps(body)}}]}

    result = check_repo.check_repo("https://github.com/owner/repo", "paper text", fake_complete)
    assert result["repo_accessible"] is True
    assert len(result["commit_sha"]) == 40
    assert (result["n_backed"], result["n_claims"]) == (1, 2)
    assert result["verdict"] is False  # 50% < 80% threshold
    assert "1/2 empirical numbers" in result["feedback"]
    assert result["claims"][0]["scan_hits"] == ["results/accuracy.csv"]
    assert "Gate 4" not in check_repo.render_gate4(result)  # detail only, no heading
    assert "results/accuracy.csv" in check_repo.render_gate4(result)
    # a failing gate always points the author at the open science recommendations
    assert f"See <{check_repo.RECOMMENDATIONS_URL}>" in check_repo.render_gate4(result)


def test_unclonable_repository_also_points_at_the_recommendations():
    result = {"repo_url": "u", "repo_accessible": False, "verdict": False, "feedback": "gone"}
    assert f"See <{check_repo.RECOMMENDATIONS_URL}>" in check_repo.render_gate4(result)


def test_passing_gate_does_not_lecture_the_author():
    result = {
        "repo_url": "u", "repo_accessible": True, "verdict": True, "feedback": "",
        "inventory": {"n_files": 3, "n_scripts": 1, "n_data": 1, "has_license": True},
        "n_claims": 1, "n_backed": 1, "traceability": 1.0, "threshold": 0.8,
        "claims": [{"value": "1", "unit": "", "claim": "c", "status": "data_file", "evidence": ["a.csv"]}],
    }
    assert check_repo.RECOMMENDATIONS_URL not in check_repo.render_gate4(result)


# --- Gate 5: osaudit.toml ---------------------------------------------------

def _osaudit_module():
    return _load(ROOT / "scripts" / "check_osaudit.py", "check_osaudit")


def _fake_bin(tmp_path: Path, code: int, out: str = "[]") -> str:
    script = tmp_path / "fake-osaudit"
    script.write_text(f"#!/bin/sh\necho '{out}'\nexit {code}\n")
    script.chmod(0o755)
    return str(script)


def test_gate5_fails_without_osaudit_toml(tmp_path: Path):
    r = _osaudit_module().check_osaudit(tmp_path, _fake_bin(tmp_path, 0))
    assert not r["verdict"] and not r["present"] and "osaudit.toml" in r["feedback"]


def test_gate5_passes_when_osaudit_is_clean(tmp_path: Path):
    (tmp_path / "osaudit.toml").write_text("")
    assert _osaudit_module().check_osaudit(tmp_path, _fake_bin(tmp_path, 0))["verdict"]


def test_gate5_fails_on_findings(tmp_path: Path):
    (tmp_path / "osaudit.toml").write_text("")
    out = '[{"file":"p.tex","line":2,"rule":"numbers/untraced","message":"392"}]'
    r = _osaudit_module().check_osaudit(tmp_path, _fake_bin(tmp_path, 1, out))
    assert not r["verdict"] and len(r["findings"]) == 1


def test_gate5_fails_when_osaudit_cannot_run(tmp_path: Path):
    (tmp_path / "osaudit.toml").write_text("")
    assert not _osaudit_module().check_osaudit(tmp_path, _fake_bin(tmp_path, 2))["verdict"]
