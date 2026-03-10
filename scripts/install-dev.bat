@echo off
REM Install skill-guard for development

echo Installing skill-guard for development...
cd /d %~dp0..

REM Install as editable Python package
pip install -e .

echo.
echo Installation complete!
echo.
echo Package: skill-guard
echo - Python library (importable)
echo - Used internally by Claude Code hooks
echo - NOT a user-facing skill
echo.
echo Next steps:
echo - Add Python code to src/skill_guard/
echo - Run tests: pytest
echo.
echo Usage in hooks:
echo   from skill_guard import discover_all_skills, get_skill_config
