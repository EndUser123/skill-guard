from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_classify_local_command_frontend(tmp_path, monkeypatch):
    import skill_guard.slash_command_observability as slash_obs

    claude_dir = tmp_path / ".claude"
    commands_dir = claude_dir / "commands"
    skills_dir = claude_dir / "skills" / "arch"
    commands_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)
    (commands_dir / "arch.md").write_text('Call Skill("arch") to load workflow', encoding="utf-8")
    (skills_dir / "SKILL.md").write_text("---\nname: arch\n---\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    result = slash_obs.classify_slash_command("arch")

    assert result["command_family"] == "local_command"
    assert result["command_path"].endswith(r".claude\commands\arch.md")
    assert result["backing_target"] == "arch"


def test_classify_skill_and_builtin(tmp_path, monkeypatch):
    import skill_guard.slash_command_observability as slash_obs

    claude_dir = tmp_path / ".claude"
    skills_dir = claude_dir / "skills" / "code"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: code\n---\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    skill_result = slash_obs.classify_slash_command("code")
    builtin_result = slash_obs.classify_slash_command("recap")

    assert skill_result["command_family"] == "skill"
    assert skill_result["backing_target"] == "code"
    assert builtin_result["command_family"] == "builtin"


def test_extract_command_name_and_prompt_normalization():
    import skill_guard.slash_command_observability as slash_obs

    assert slash_obs.extract_command_name("❯ /arch do the thing") == "arch"
    assert slash_obs.normalize_prompt("❯ /arch do the thing").startswith("/arch")
    assert slash_obs.is_slash_prompt("/arch do the thing") is True


def test_record_slash_request_emits_event(monkeypatch):
    import skill_guard.slash_command_observability as slash_obs

    events: list[dict] = []

    class Context:
        prompt = "/arch build a plan"
        session_id = "session-1"
        terminal_id = "terminal-1"
        data = {"turn_id": "turn-1"}

    monkeypatch.setattr(slash_obs, "append_tool_event", lambda **kwargs: events.append(kwargs) or True)
    monkeypatch.setattr(slash_obs, "resolve_session_id", lambda explicit="": explicit or "session-1")
    monkeypatch.setattr(slash_obs, "get_active_turn", lambda session_id, terminal_id: "turn-1")
    monkeypatch.setattr(slash_obs, "classify_slash_command", lambda command: {
        "command_name": command,
        "command_family": "skill",
        "command_path": r"P:\\\\packages/skill-guard/src/skill_guard/skills/arch/SKILL.md",
        "backing_target": "arch",
    })

    assert slash_obs.record_slash_request(Context(), "arch", "build a plan") is True
    assert events
    assert events[0]["tool_name"] == "SlashCommandRequested"
    assert events[0]["metadata"]["command_family"] == "skill"
    assert events[0]["metadata"]["command_name"] == "arch"
