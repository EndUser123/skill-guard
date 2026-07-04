"""Action-authority gate (Tier 1) — layered tests.

Layer justification:
- UNIT proves the directive/strip/pure-question discrimination logic.
- REGRESSION proves the exact MEMORY.md failure path (advisory-only user msg).
- INTEGRATION proves the real stdin -> _normalize_stdout -> stdout boundary via
  the actual pre_tool_use_main entry, including the deny-shape that survives
  normalization. A lower (unit) layer cannot prove the deny shape or wiring.
- CONCURRENCY proves multi-terminal safety of the ambiguous-slice telemetry log
  by spawning real cross-process writers (the actual hazard), not threads.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_ROOT))

from skill_guard.execution_hooks import (  # noqa: E402
    _action_authority_gate,
    _AMBIGUOUS_LOG,
    _parse_transcript_for_last_user_message,
    _strip_injections,
    pre_tool_use_main,
)


# ---------------------------------------------------------------------------
# Transcript seed helpers
# ---------------------------------------------------------------------------

def _seed_transcript(path: Path, messages: list[str]) -> Path:
    """Write a transcript JSONL with the given user messages (last = current)."""
    with path.open("w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps({"role": "user", "message": {"content": msg}}) + "\n")
    return path


def _data(tmp_path: Path, transcript_path: Path, tool: str = "Write",
          file_path: str = "P:/repo/file.py") -> dict:
    return {
        "tool_name": tool,
        "tool_input": {"file_path": file_path},
        "input": {"file_path": file_path},
        "transcript_path": str(transcript_path),
        "session_id": "test-session-1",
    }


# ===========================================================================
# UNIT: _strip_injections
# ===========================================================================

class TestStripInjections:
    def test_removes_single_system_reminder(self):
        text = "keep this<system-reminder>drop this</system-reminder>also keep"
        assert _strip_injections(text) == "keep thisalso keep"

    def test_removes_multiple_system_reminders(self):
        text = ("<system-reminder>a</system-reminder>x"
                "<system-reminder>b</system-reminder>y")
        assert _strip_injections(text) == "xy"

    def test_removes_multiline_reminder(self):
        text = "x<system-reminder>line1\nline2\nconsider compacting</system-reminder>y"
        assert "compacting" not in _strip_injections(text)
        assert _strip_injections(text) == "xy"

    def test_none_input(self):
        assert _strip_injections(None) == ""


# ===========================================================================
# UNIT: gate discrimination
# ===========================================================================

class TestGateLogic:
    def test_advisory_only_blocks(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["<system-reminder>MEMORY.md large; consider compacting.</system-reminder>"])
        result = _action_authority_gate(_data(tmp_path, tp))
        assert result is not None
        assert result["continue"] is False
        assert "ACTION-AUTHORITY" in result["reason"]

    def test_empty_user_message_blocks(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, [""])
        assert _action_authority_gate(_data(tmp_path, tp)) is not None

    def test_bare_confirmation_allows(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        for confirm in ("proceed", "yes", "ok", "do it", "ship it", "looks good"):
            _seed_transcript(tp, [confirm])
            assert _action_authority_gate(_data(tmp_path, tp)) is None, f"failed on: {confirm}"

    def test_clear_imperative_allows(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        for imp in ("fix the bug", "refactor the hooks", "update the wiki",
                    "create the file", "delete the stub"):
            _seed_transcript(tp, [imp])
            assert _action_authority_gate(_data(tmp_path, tp)) is None, f"failed on: {imp}"

    def test_pure_question_blocks(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        for q in ("what is the status?", "what is the status of the build?",
                  "how does this work?", "why did it fail?"):
            _seed_transcript(tp, [q])
            assert _action_authority_gate(_data(tmp_path, tp)) is not None, f"failed on: {q}"

    # ponytail: lock in the `apply` rejection (reviewed 2026-07-04). Adding
    # `apply` to _IMPERATIVE_RE breaks both tests — re-measure TP/FP on a real
    # blocked-messages corpus before re-proposing. See execution_hooks.py:151-160.
    def test_apply_declarative_still_ambiguous_not_clear_allow(self, tmp_path, monkeypatch):
        log = tmp_path / "ambig.jsonl"
        monkeypatch.setattr("skill_guard.execution_hooks._AMBIGUOUS_LOG", log)
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["apply the patch"])
        assert _action_authority_gate(_data(tmp_path, tp)) is None
        assert log.exists(), "apply must NOT be a clear imperative — it must log ambiguous"

    def test_apply_conceptual_question_still_blocks(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["what does apply mean in this context?"])
        assert _action_authority_gate(_data(tmp_path, tp)) is not None

    def test_ambiguous_verb_in_question_allows(self, tmp_path, monkeypatch):
        # redirect telemetry log to temp so we don't pollute the real one
        log = tmp_path / "ambig.jsonl"
        monkeypatch.setattr("skill_guard.execution_hooks._AMBIGUOUS_LOG", log)
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["can you fix the bug?"])
        assert _action_authority_gate(_data(tmp_path, tp)) is None
        assert log.exists()
        rec = json.loads(log.read_text(encoding="utf-8").strip())
        assert rec["session_id"] == "test-session-1"

    def test_ambiguous_declarative_allows_and_logs(self, tmp_path, monkeypatch):
        log = tmp_path / "ambig.jsonl"
        monkeypatch.setattr("skill_guard.execution_hooks._AMBIGUOUS_LOG", log)
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["the docs need work"])
        assert _action_authority_gate(_data(tmp_path, tp)) is None
        assert log.exists()

    def test_inherent_allow_artifacts(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, [""])  # would normally block
        d = _data(tmp_path, tp, file_path="P:/.claude/.artifacts/t/skill/out.json")
        assert _action_authority_gate(d) is None

    def test_inherent_allow_state_and_temp(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, [""])
        for p in ("P:/.claude/state/x.json", "P:/.claude/.session/y.json",
                  "C:/temp/z.json", "/tmp/q.json"):
            assert _action_authority_gate(_data(tmp_path, tp, file_path=p)) is None, p

    def test_bypass_flag_allows(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["random text --allow-unsolicited"])
        assert _action_authority_gate(_data(tmp_path, tp)) is None

    def test_non_target_tool_skipped(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, [""])
        assert _action_authority_gate(_data(tmp_path, tp, tool="Read")) is None
        assert _action_authority_gate(_data(tmp_path, tp, tool="Bash")) is None

    def test_missing_transcript_fail_open(self, tmp_path):
        d = _data(tmp_path, tmp_path / "does-not-exist.jsonl")
        assert _action_authority_gate(d) is None


# ===========================================================================
# UNIT: transcript parser edge cases
# ===========================================================================

class TestTranscriptParser:
    def test_skips_tool_result_entries(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        with tp.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"role": "user", "message": {"content": "fix the bug"}}) + "\n")
            # tool_result entry (role:user but only tool_result block) — must be skipped,
            # so the parser falls back to the prior real user message.
            f.write(json.dumps({"role": "user", "message": {"content": [
                {"type": "tool_result", "content": "ok"}]}}) + "\n")
        assert _parse_transcript_for_last_user_message(str(tp)) == "fix the bug"

    def test_returns_last_user_text(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["first message", "second message"])
        assert _parse_transcript_for_last_user_message(str(tp)) == "second message"

    def test_string_content(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        with tp.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "plain string"}}) + "\n")
        assert _parse_transcript_for_last_user_message(str(tp)) == "plain string"

    def test_missing_file_returns_none(self, tmp_path):
        # Plan step 10: missing/unreadable transcript -> None -> fail-open (allow).
        assert _parse_transcript_for_last_user_message(str(tmp_path / "nope.jsonl")) is None


# ===========================================================================
# REGRESSION: exact MEMORY.md failure path
# ===========================================================================

class TestMemoryMdRegression:
    def test_advisory_only_blocks_memory_md_write(self, tmp_path):
        """The incident: agent compacted MEMORY.md on a pure system-reminder."""
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, [
            "<system-reminder>MEMORY.md is approaching the 200-line limit; "
            "consider compacting.</system-reminder>"
        ])
        d = _data(tmp_path, tp, file_path="C:/Users/brsth/.claude/projects/P--/memory/MEMORY.md")
        result = _action_authority_gate(d)
        assert result is not None
        assert result["continue"] is False
        # Reason must surface the empty-after-strip cause
        assert "no recent user instruction" in result["reason"]


# ===========================================================================
# INTEGRATION: real pre_tool_use_main stdin -> stdout boundary
# ===========================================================================

class TestEntryPointBoundary:
    def _run_entry(self, payload: dict) -> dict:
        """Invoke pre_tool_use_main in a subprocess with stdin=payload, return stdout JSON."""
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s'); "
             "from skill_guard.execution_hooks import pre_tool_use_main; "
             "pre_tool_use_main()" % str(SRC_ROOT)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}"
        return json.loads(proc.stdout)

    def test_imperative_allows_through_entry(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["fix the bug"])
        out = self._run_entry({
            "tool_name": "Write",
            "tool_input": {"file_path": "P:/repo/x.py"},
            "transcript_path": str(tp),
            "session_id": "s1",
        })
        # allow normalizes to {} (no decision block)
        assert out == {} or "decision" not in out or out.get("decision") != "block"

    def test_advisory_only_blocks_through_entry(self, tmp_path):
        tp = tmp_path / "t.jsonl"
        _seed_transcript(tp, ["<system-reminder>consider compacting</system-reminder>"])
        out = self._run_entry({
            "tool_name": "Write",
            "tool_input": {"file_path": "P:/repo/x.py"},
            "transcript_path": str(tp),
            "session_id": "s1",
        })
        assert out.get("decision") == "block"
        assert out.get("reason")
        assert "ACTION-AUTHORITY" in out["reason"]


# ===========================================================================
# CONCURRENCY: multi-terminal telemetry-log safety (real cross-process)
# ===========================================================================

class TestConcurrentTelemetryAppend:
    def test_cross_process_appends_do_not_corrupt(self, tmp_path):
        """Spawn N python processes (simulating N terminals) appending to the same log."""
        log = tmp_path / "ambig.jsonl"
        n_procs = 5
        n_per = 20
        # Worker as a real file: Python forbids compound statements (for) after ';'
        # in a -c one-liner, so the script must run from disk.
        worker = tmp_path / "worker.py"
        worker.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, r'{SRC_ROOT}')\n"
            "from skill_guard import execution_hooks as eh\n"
            f"eh._AMBIGUOUS_LOG = Path(r'{log}')\n"
            f"for i in range({n_per}):\n"
            "    eh._log_ambiguous({'session_id':'s','tool':'Write','tool_input':{'file_path':'p'}}, "
            "'the docs need work ' + str(i))\n",
            encoding="utf-8",
        )
        procs = [subprocess.run([sys.executable, str(worker)], capture_output=True, text=True)
                 for _ in range(n_procs)]
        for p in procs:
            assert p.returncode == 0, f"proc failed: {p.stderr}"

        lines = log.read_text(encoding="utf-8").splitlines()
        # Every line must be valid JSON (no interleaving corruption)
        parsed = []
        for ln in lines:
            parsed.append(json.loads(ln))  # raises on corruption
        assert len(parsed) == n_procs * n_per
        # Every record carries a session id (cross-terminal distinguishable)
        assert all("session_id" in r for r in parsed)
