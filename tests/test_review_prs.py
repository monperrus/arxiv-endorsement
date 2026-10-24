"""Tests for the pull-request handling in review_prs.py (no network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review_prs = _load(ROOT / "scripts" / "review_prs.py", "review_prs")

WRONG_SUBJECT = "LinkedIn: https://www.linkedin.com/in/someone\nPaper: https://example.org/p.pdf\nRepo: https://github.com/someone/repo\nSubject: cs.AI\nEndorsementCode: A1B2C3\n"
MALFORMED = "LinkedIn: https://www.linkedin.com/in/someone\nSubject: cs.SE\n"
VALID = "LinkedIn: https://www.linkedin.com/in/someone\nPaper: https://example.org/p.pdf\nRepo: https://github.com/someone/repo\nSubject: cs.SE\nEndorsementCode: A1B2C3\n"

PR = {"number": 42, "files": [{"path": "requests/someone.txt"}], "headRefOid": "deadbeef", "author": {"login": "someone"}}


@pytest.fixture
def stubbed(monkeypatch):
    calls: dict[str, list] = {"comments": [], "closed": [], "commented_markers": []}
    monkeypatch.setattr(review_prs, "post_comment", lambda repo, n, body: calls["comments"].append((n, body)))
    monkeypatch.setattr(review_prs, "already_commented", lambda repo, n, marker=review_prs.COMMENT_MARKER: False)
    monkeypatch.setattr(review_prs, "find_comment", lambda repo, n, marker=review_prs.COMMENT_MARKER: None)
    monkeypatch.setattr(review_prs, "author_replied_since_check", lambda repo, n, author: False)

    def fake_close(repo, n, body):
        calls["comments"].append((n, body))
        calls["closed"].append(n)

    monkeypatch.setattr(review_prs, "close_pr", fake_close)
    return calls


def test_wrong_subject_pr_is_closed_with_the_automated_reply(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: WRONG_SUBJECT)
    review_prs.process_pr("owner/repo", PR, dry_run=False, update=False)
    assert stubbed["closed"] == [42]
    (_, body), = stubbed["comments"]
    assert review_prs.WRONG_SUBJECT_MESSAGE in body
    assert review_prs.WRONG_SUBJECT_MARKER in body


def test_wrong_subject_pr_is_not_closed_in_dry_run(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: WRONG_SUBJECT)
    review_prs.process_pr("owner/repo", PR, dry_run=True, update=False)
    assert stubbed["closed"] == []
    assert stubbed["comments"] == []


def test_wrong_subject_pr_is_answered_only_once(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: WRONG_SUBJECT)
    monkeypatch.setattr(
        review_prs, "already_commented",
        lambda repo, n, marker=review_prs.COMMENT_MARKER: marker == review_prs.WRONG_SUBJECT_MARKER,
    )
    review_prs.process_pr("owner/repo", PR, dry_run=False, update=False)
    assert stubbed["closed"] == []
    assert stubbed["comments"] == []


class _Proc:
    def __init__(self, code, out):
        self.returncode, self.stdout, self.stderr = code, out, ""


def test_completion_uses_best_effort_medium_tier(monkeypatch, tmp_path):
    backend = tmp_path / "best-effort-completions.py"
    backend.write_text("")
    monkeypatch.setattr(review_prs, "COMPLETION_BACKEND", backend)

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[1:])
        return _Proc(0, '{"model": "x", "best_effort": {"model": "claude-sonnet-5-5"}, "choices": []}')

    monkeypatch.setattr(review_prs.subprocess, "run", fake_run)
    monkeypatch.setattr(review_prs, "_PINNED_MODEL", None)
    review_prs.best_effort_completion({"messages": []})
    assert calls == [[str(backend), "--tier", "medium"]]
    assert "claude-sonnet-5-5" in review_prs._MODELS_USED


def test_completion_pins_the_first_model_for_later_calls(monkeypatch, tmp_path):
    backend = tmp_path / "best-effort-completions.py"
    backend.write_text("")
    monkeypatch.setattr(review_prs, "COMPLETION_BACKEND", backend)
    monkeypatch.setattr(review_prs, "_PINNED_MODEL", None)
    monkeypatch.setattr(review_prs, "backend_model_names", lambda: {"cursor-composer-completions.py": "composer-2.5"})
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[2:])
        return _Proc(0, '{"best_effort": {"backend": "cursor-composer-completions.py", "model": "composer-2.5"}}')

    monkeypatch.setattr(review_prs.subprocess, "run", fake_run)
    review_prs._MODELS_USED.clear()
    review_prs.best_effort_completion({"messages": []})
    review_prs.best_effort_completion({"messages": []})
    assert calls == [["--tier", "medium"], ["--model", "composer-2.5"]]
    assert review_prs._MODELS_USED == ["composer-2.5"]


def test_completion_falls_back_to_the_tier_when_the_pinned_model_fails(monkeypatch, tmp_path):
    backend = tmp_path / "best-effort-completions.py"
    backend.write_text("")
    monkeypatch.setattr(review_prs, "COMPLETION_BACKEND", backend)
    monkeypatch.setattr(review_prs, "_PINNED_MODEL", "composer-2.5")
    monkeypatch.setattr(review_prs, "backend_model_names", lambda: {"kimi-k3-completions.py": "kimi-k3"})
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd[2:])
        if "--model" in cmd:
            return _Proc(1, "")
        return _Proc(0, '{"best_effort": {"backend": "kimi-k3-completions.py", "model": "kimi-k3"}}')

    monkeypatch.setattr(review_prs.subprocess, "run", fake_run)
    review_prs.best_effort_completion({"messages": []})
    assert calls == [["--model", "composer-2.5"], ["--tier", "medium"]]
    assert review_prs._PINNED_MODEL == "kimi-k3"


def test_backend_model_names_reads_the_real_backend():
    if not review_prs.COMPLETION_BACKEND.exists():
        pytest.skip("best-effort-completions.py not installed")
    names = review_prs.backend_model_names()
    assert names["cursor-composer-completions.py"] == "composer-2.5"
    assert names["openai-completions.py --model gpt-5.6-terra"] == "gpt-5.6-terra"


def test_completion_raises_when_backend_fails(monkeypatch, tmp_path):
    backend = tmp_path / "best-effort-completions.py"
    backend.write_text("")
    monkeypatch.setattr(review_prs, "COMPLETION_BACKEND", backend)
    monkeypatch.setattr(review_prs.subprocess, "run", lambda cmd, **kw: _Proc(75, '{"error": {}}'))
    with pytest.raises(RuntimeError, match="no completion backend succeeded"):
        review_prs.best_effort_completion({"messages": []})


def test_completion_raises_when_backend_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(review_prs, "COMPLETION_BACKEND", tmp_path / "missing.py")
    with pytest.raises(RuntimeError, match="no completion backend succeeded"):
        review_prs.best_effort_completion({"messages": []})


def test_format_messages_flattens_roles_and_content():
    payload = {
        "messages": [
            {"role": "system", "content": "be strict"},
            {"role": "user", "content": "evaluate this"},
        ]
    }
    assert review_prs.format_messages(payload["messages"]) == "SYSTEM:\nbe strict\n\nUSER:\nevaluate this"


def test_agent_completion_wraps_stdout_as_openai_response(monkeypatch, tmp_path):
    script = tmp_path / "agent-kimi-k3.py"
    script.write_text("")
    seen: dict = {}

    class Proc:
        returncode = 0
        stdout = '{"overall_verdict": true}\n'
        stderr = ""

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["input"] = kwargs["input"]
        return Proc()

    monkeypatch.setattr(review_prs.subprocess, "run", fake_run)
    review_prs._MODELS_USED.clear()
    response = review_prs.agent_completion(
        {"messages": [{"role": "user", "content": "hi"}]}, script, "kimi-k3 (agentknit)"
    )
    assert seen["cmd"] == [review_prs.sys.executable, str(script), "--non-interactive"]
    assert "USER:\nhi" in seen["input"]
    assert "ONLY the requested JSON" in seen["input"]
    assert response["choices"][0]["message"]["content"] == '{"overall_verdict": true}'
    assert review_prs._LAST_MODEL == "kimi-k3 (agentknit)"
    assert "kimi-k3 (agentknit)" in review_prs._MODELS_USED


def test_agent_completion_tolerates_agentknit_console_noise(monkeypatch, tmp_path):
    script = tmp_path / "agent-kimi-k3.py"
    script.write_text("")

    class Proc:
        returncode = 0
        stdout = (
            "\x1b[2m\x1b[35m[budget] 1,047,136/1,048,576 tokens remaining\x1b[0m\n"
            "\x1b[2m\x1b[35m[tokens] prompt 1,440\x1b[0m\n\n"
            "I'll evaluate the paper now.\n"
            '{"overall_verdict": true}\n'
            "\x1b[2m\x1b[35m[session tokens] prompt 1,440\x1b[0m\n"
        )
        stderr = ""

    monkeypatch.setattr(review_prs.subprocess, "run", lambda *a, **k: Proc())
    response = review_prs.agent_completion(
        {"messages": [{"role": "user", "content": "hi"}]}, script, "kimi-k3 (agentknit)"
    )
    parsed = review_prs.check_paper.parse_evaluation_response(response)
    assert parsed == {"overall_verdict": True}


def test_agent_completion_raises_when_no_json_in_output(monkeypatch, tmp_path):
    script = tmp_path / "agent-kimi-k3.py"
    script.write_text("")

    class Proc:
        returncode = 0
        stdout = "The agent chatted but produced no JSON.\n"
        stderr = ""

    monkeypatch.setattr(review_prs.subprocess, "run", lambda *a, **k: Proc())
    with pytest.raises(RuntimeError, match="could not parse JSON"):
        review_prs.agent_completion({"messages": []}, script, "kimi-k3 (agentknit)")


def test_agent_completion_raises_on_nonzero_exit(monkeypatch, tmp_path):
    script = tmp_path / "agent-kimi-k3.py"
    script.write_text("")

    class Proc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(review_prs.subprocess, "run", lambda *a, **k: Proc())
    with pytest.raises(RuntimeError, match="boom"):
        review_prs.agent_completion({"messages": []}, script, "kimi-k3 (agentknit)")


def test_agent_completion_raises_when_script_missing(tmp_path):
    with pytest.raises(RuntimeError, match="agent script not found"):
        review_prs.agent_completion({"messages": []}, tmp_path / "nope.py", "x")


def test_make_completion_defaults_to_claude_backends():
    assert review_prs.make_completion("claude") is review_prs.best_effort_completion


def test_make_completion_returns_agent_lambda():
    complete = review_prs.make_completion("kimi-k3")
    assert complete is not review_prs.best_effort_completion
    assert callable(complete)


def test_other_validation_errors_leave_the_pr_open(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: MALFORMED)
    review_prs.process_pr("owner/repo", PR, dry_run=False, update=False)
    assert stubbed["closed"] == []
    assert stubbed["comments"] == []


NOW = review_prs.datetime(2026, 10, 19, tzinfo=review_prs.timezone.utc)
FAILING_CHECK = {"body": f"{review_prs.COMMENT_MARKER}\n- ✓ PASS gate 1\n- ✗ FAIL gate 2", "url": "x#issuecomment-1"}
PASSING_CHECK = {"body": f"{review_prs.COMMENT_MARKER}\n- ✓ PASS gate 1\n- ✓ PASS gate 2", "url": "x#issuecomment-1"}


def _pr_updated(days_ago: int) -> dict:
    updated = NOW - review_prs.timedelta(days=days_ago)
    return {**PR, "updatedAt": updated.strftime("%Y-%m-%dT%H:%M:%SZ")}


@pytest.mark.parametrize(
    ("check", "days_ago", "closed"),
    [(FAILING_CHECK, 15, True), (FAILING_CHECK, 14, True), (FAILING_CHECK, 13, False), (PASSING_CHECK, 30, False)],
)
def test_inactive_pr_with_a_failing_gate_is_autoclosed(stubbed, monkeypatch, check, days_ago, closed):
    monkeypatch.setattr(review_prs, "find_comment", lambda repo, n, marker=review_prs.COMMENT_MARKER: check)
    review_prs.process_pr("owner/repo", _pr_updated(days_ago), dry_run=False, update=False, now=NOW)
    assert stubbed["closed"] == ([42] if closed else [])
    if closed:
        (_, body), = stubbed["comments"]
        assert review_prs.AUTOCLOSE_MESSAGE in body
        assert review_prs.AUTOCLOSE_MARKER in body
    else:
        assert stubbed["comments"] == []


def test_autoclose_is_not_applied_in_dry_run(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "find_comment", lambda repo, n, marker=review_prs.COMMENT_MARKER: FAILING_CHECK)
    review_prs.process_pr("owner/repo", _pr_updated(30), dry_run=True, update=False, now=NOW)
    assert stubbed["closed"] == []
    assert stubbed["comments"] == []


def test_pr_is_not_autoclosed_when_the_author_replied(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "find_comment", lambda repo, n, marker=review_prs.COMMENT_MARKER: FAILING_CHECK)
    monkeypatch.setattr(review_prs, "author_replied_since_check", lambda repo, n, author: author == "someone")
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: MALFORMED)
    review_prs.process_pr("owner/repo", _pr_updated(30), dry_run=False, update=False, now=NOW)
    assert stubbed["closed"] == []


def _comments_api(monkeypatch, comments: list[dict]) -> None:
    lines = "\n".join(review_prs.json.dumps(c) for c in comments)
    monkeypatch.setattr(review_prs.subprocess, "run", lambda cmd, **kw: _Proc(0, lines))


@pytest.mark.parametrize(
    ("comments", "replied"),
    [
        # author asked for a re-check after our check comment
        ([{"login": "bot", "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z", "body": review_prs.COMMENT_MARKER},
          {"login": "someone", "created_at": "2026-10-02T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z", "body": "fixed"}], True),
        # a later re-check comment was posted after the author's reply
        ([{"login": "bot", "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-03T00:00:00Z", "body": review_prs.COMMENT_MARKER},
          {"login": "someone", "created_at": "2026-10-02T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z", "body": "fixed"}], False),
        # someone else replied
        ([{"login": "bot", "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z", "body": review_prs.COMMENT_MARKER},
          {"login": "other", "created_at": "2026-10-02T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z", "body": "+1"}], False),
    ],
)
def test_author_replied_since_check(monkeypatch, comments, replied):
    _comments_api(monkeypatch, comments)
    assert review_prs.author_replied_since_check("owner/repo", 42, "someone") is replied


def test_update_never_autocloses(stubbed, monkeypatch):
    monkeypatch.setattr(review_prs, "find_comment", lambda repo, n, marker=review_prs.COMMENT_MARKER: FAILING_CHECK)
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: MALFORMED)
    review_prs.process_pr("owner/repo", _pr_updated(30), dry_run=False, update=True, now=NOW)
    assert stubbed["closed"] == []


def test_update_posts_a_new_check_comment(stubbed, monkeypatch, tmp_path):
    """A re-check preserves the earlier assessment as an auditable record."""
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"pdf")
    existing = {"body": review_prs.COMMENT_MARKER, "url": "x#issuecomment-1"}
    monkeypatch.setattr(review_prs, "find_comment", lambda repo, n, marker=review_prs.COMMENT_MARKER: existing)
    monkeypatch.setattr(review_prs, "fetch_file_content", lambda repo, path, ref: VALID)
    monkeypatch.setattr(review_prs.check_paper, "download_pdf", lambda url: paper)
    monkeypatch.setattr(review_prs.check_paper, "sha256_file", lambda path: "checksum")
    monkeypatch.setattr(review_prs.check_paper, "pdf_to_text", lambda path: "paper text")
    monkeypatch.setattr(review_prs, "evaluate_paper", lambda text, complete: (_gate_result(), "model"))
    monkeypatch.setattr(review_prs, "build_comment", lambda *args: "new assessment")

    review_prs.process_pr("owner/repo", PR, dry_run=False, update=True, skip_repo=True)

    assert stubbed["comments"] == [(42, "new assessment")]


def _gate_result(verdict: bool = True) -> dict:
    return {
        key: {"verdict": verdict, "confidence": "high", "feedback": ""}
        for key, _ in review_prs.check_paper.GATES
    }


def test_build_comment_includes_the_repo_commit_sha():
    result = _gate_result()
    result["summary"] = ""
    repo_result = {"verdict": True, "confidence": "high", "commit_sha": "abc1234def5678901234567890123456789abcd"}
    comment = review_prs.build_comment(
        result, "https://arxiv.org/abs/1", "https://github.com/owner/repo", "model", "checksum", repo_result,
    )
    assert "Repo: https://github.com/owner/repo @ `abc1234def5678901234567890123456789abcd`" in comment


def test_build_comment_omits_commit_sha_when_absent():
    result = _gate_result()
    result["summary"] = ""
    comment = review_prs.build_comment(
        result, "https://arxiv.org/abs/1", "https://github.com/owner/repo", "model", "checksum", None,
    )
    assert "Repo: https://github.com/owner/repo\n" in comment
    assert "@" not in comment
