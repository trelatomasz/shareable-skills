"""Unit tests for the shskills CLI (typer commands)."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from shskills._version import __version__
from shskills.cli import app
from shskills.exceptions import FetchError
from shskills.models import (
    DoctorIssue,
    DoctorReport,
    DoctorSeverity,
    ExportResult,
    InstalledSkill,
    InstallResult,
    SkillFrontmatter,
    SkillInfo,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------


class TestVersionFlag:
    def test_prints_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
        assert "shskill" in result.output

    def test_skill_link_option(self) -> None:
        result = runner.invoke(app, ["--skill"])
        assert result.exit_code == 0
        assert "https://github.com/trelatomasz/shskills" in result.output

    def test_install_self_bootstraps_agent_skills(self, tmp_path: Path) -> None:
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["--install", "self"])

        assert result.exit_code == 0
        assert (tmp_path / ".claude/skills/shskills/SKILL.md").is_file()
        assert (tmp_path / ".agents/skills/shskills/SKILL.md").is_file()
        assert (tmp_path / ".gemini/skills/shskills/SKILL.md").is_file()

    def test_install_self_command(self, tmp_path: Path) -> None:
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["install", "self", "--agent", "antigravity"])

        assert result.exit_code == 0
        assert (tmp_path / ".agents/skills/shskills/SKILL.md").is_file()


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


class TestInstallCommand:
    def test_missing_url_exits_nonzero(self) -> None:
        result = runner.invoke(app, ["install", "--agent", "claude"])
        assert result.exit_code != 0

    def test_successful_install_shows_installed(self, tmp_path: Path) -> None:
        mock_result = InstallResult(installed=["common/welcome_note"])
        with patch("shskills.core.installer.install", return_value=mock_result):
            result = runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--agent",
                    "claude",
                    "--dest",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0
        assert "installed" in result.output

    def test_skill_name_is_passed_through(self, tmp_path: Path) -> None:
        captured: dict[str, object] = {}

        def fake_install(**kwargs: object) -> InstallResult:
            captured.update(kwargs)
            return InstallResult(installed=["learning-session"])

        with patch("shskills.core.installer.install", side_effect=fake_install):
            result = runner.invoke(
                app,
                [
                    "install",
                    "learning-session",
                    "--url",
                    "https://github.com/x/y",
                    "--dest",
                    str(tmp_path),
                ],
            )

        assert result.exit_code == 0
        assert captured["skills"] == ("learning-session",)

    def test_dry_run_flag_passes_through(self, tmp_path: Path) -> None:
        mock_result = InstallResult(installed=["skill_a"])
        captured: dict[str, object] = {}

        def fake_install(**kwargs: object) -> InstallResult:
            captured.update(kwargs)
            return mock_result

        with patch("shskills.core.installer.install", side_effect=fake_install):
            runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--dest",
                    str(tmp_path),
                    "--dry-run",
                ],
            )

        assert captured.get("dry_run") is True

    def test_conflict_shows_force_hint(self, tmp_path: Path) -> None:
        mock_result = InstallResult(conflicts=["some/skill"])
        with patch("shskills.core.installer.install", return_value=mock_result):
            result = runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--dest",
                    str(tmp_path),
                ],
            )
        assert "--force" in result.output

    def test_errors_exit_code_1(self, tmp_path: Path) -> None:
        mock_result = InstallResult(errors=["skill/x: permission denied"])
        with patch("shskills.core.installer.install", return_value=mock_result):
            result = runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--dest",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 1

    def test_nothing_to_do_message(self, tmp_path: Path) -> None:
        mock_result = InstallResult(skipped=["a", "b"])
        with patch("shskills.core.installer.install", return_value=mock_result):
            result = runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--dest",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0
        assert "Nothing to do" in result.output

    def test_fetch_error_shown_and_exits_1(self, tmp_path: Path) -> None:
        with patch(
            "shskills.core.installer.install",
            side_effect=FetchError("repo not found"),
        ):
            result = runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--dest",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 1

    def test_all_flags_passed_through(self, tmp_path: Path) -> None:
        captured: dict[str, object] = {}

        def fake_install(**kwargs: object) -> InstallResult:
            captured.update(kwargs)
            return InstallResult()

        with patch("shskills.core.installer.install", side_effect=fake_install):
            runner.invoke(
                app,
                [
                    "install",
                    "--url",
                    "https://github.com/x/y",
                    "--agent",
                    "codex",
                    "--subpath",
                    "aws",
                    "--ref",
                    "v1.0",
                    "--dest",
                    str(tmp_path),
                    "--force",
                    "--clean",
                    "--strict",
                    "--verbose",
                ],
            )

        assert captured["agent"] == "codex"
        assert captured["subpath"] == "aws"
        assert captured["ref"] == "v1.0"
        assert captured["force"] is True
        assert captured["clean"] is True
        assert captured["strict"] is True
        assert captured["verbose"] is True


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_shows_table_with_skills(self) -> None:
        mock_skills = [
            SkillInfo(
                name="welcome_note",
                rel_path="common/welcome_note",
                source_rel="common/welcome_note",
                local_path=Path("/tmp/x"),
                frontmatter=SkillFrontmatter(
                    name="welcome_note", description="A welcome", version="1.0.0"
                ),
                files=["SKILL.md"],
                content_sha256="a" * 64,
            )
        ]
        with patch("shskills.core.planner.list_skills", return_value=mock_skills):
            result = runner.invoke(
                app,
                ["list", "--url", "https://github.com/x/y"],
            )
        assert result.exit_code == 0
        assert "welcome_note" in result.output

    def test_empty_shows_no_skills_message(self) -> None:
        with patch("shskills.core.planner.list_skills", return_value=[]):
            result = runner.invoke(app, ["list", "--url", "https://github.com/x/y"])
        assert result.exit_code == 0
        assert "No skills" in result.output

    def test_fetch_error_exits_1(self) -> None:
        with patch(
            "shskills.core.planner.list_skills",
            side_effect=FetchError("not found"),
        ):
            result = runner.invoke(app, ["list", "--url", "https://github.com/x/y"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# installed
# ---------------------------------------------------------------------------


class TestInstalledCommand:
    def test_no_skills_shows_message(self, tmp_path: Path) -> None:
        with patch("shskills.core.manifest.installed_skills", return_value=[]):
            result = runner.invoke(app, ["installed", "--agent", "claude", "--dest", str(tmp_path)])
        assert result.exit_code == 0
        assert "No skills" in result.output

    def test_shows_table_when_skills_present(self, tmp_path: Path) -> None:
        from datetime import datetime

        mock_skills = [
            InstalledSkill(
                name="welcome_note",
                source_path="common/welcome_note",
                dest_path=".claude/skills/welcome_note",
                content_sha256="a" * 64,
                installed_at=datetime(2026, 1, 1, tzinfo=UTC),
                files=["SKILL.md"],
            )
        ]
        with patch("shskills.core.manifest.installed_skills", return_value=mock_skills):
            result = runner.invoke(app, ["installed", "--agent", "claude", "--dest", str(tmp_path)])
        assert result.exit_code == 0
        assert "welcome_note" in result.output




# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


class TestDoctorCommand:
    def test_healthy_exits_0(self, tmp_path: Path) -> None:
        mock_report = DoctorReport(agent="claude", dest=tmp_path, installed_count=2, issues=[])
        with patch("shskills.core.installer.doctor", return_value=mock_report):
            result = runner.invoke(app, ["doctor", "--agent", "claude", "--dest", str(tmp_path)])
        assert result.exit_code == 0
        assert "All good" in result.output

    def test_unhealthy_exits_1(self, tmp_path: Path) -> None:
        mock_report = DoctorReport(
            agent="claude",
            dest=tmp_path,
            installed_count=1,
            issues=[DoctorIssue(severity=DoctorSeverity.ERROR, message="missing dir")],
        )
        with patch("shskills.core.installer.doctor", return_value=mock_report):
            result = runner.invoke(app, ["doctor", "--agent", "claude", "--dest", str(tmp_path)])
        assert result.exit_code == 1
        assert "missing dir" in result.output

    def test_warning_exits_0(self, tmp_path: Path) -> None:
        mock_report = DoctorReport(
            agent="claude",
            dest=tmp_path,
            installed_count=1,
            issues=[DoctorIssue(severity=DoctorSeverity.WARNING, message="hash mismatch")],
        )
        with patch("shskills.core.installer.doctor", return_value=mock_report):
            result = runner.invoke(app, ["doctor", "--agent", "claude", "--dest", str(tmp_path)])
        assert result.exit_code == 0
        assert "hash mismatch" in result.output


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


class TestExportCommand:
    def test_export_success(self, tmp_path: Path) -> None:
        mock_res = ExportResult(exported=["atlas", "info"])
        with patch("shskills.core.exporter.export_skills", return_value=mock_res):
            result = runner.invoke(app, ["export", "--agent", "codex", "--dest", str(tmp_path)])
        assert result.exit_code == 0
        assert "exported" in result.output
        assert "2 exported" in result.output

    def test_export_conflicts_exits_nonzero(self, tmp_path: Path) -> None:
        mock_res = ExportResult(conflicts=["atlas"])
        with patch("shskills.core.exporter.export_skills", return_value=mock_res):
            result = runner.invoke(app, ["export", "--agent", "codex", "--dest", str(tmp_path)])
        assert result.exit_code == 1
        assert "conflict" in result.output


# ---------------------------------------------------------------------------
# install with --path
# ---------------------------------------------------------------------------


class TestInstallPathCommand:
    def test_install_both_url_and_path_errors(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["install", "--url", "https://github.com/foo/bar", "--path", str(tmp_path)])
        assert result.exit_code != 0
        assert "Specify either --url or --path, not both" in result.output

    def test_install_path_success(self, tmp_path: Path) -> None:
        mock_result = InstallResult(installed=["atlas"])
        with patch("shskills.core.installer.install", return_value=mock_result):
            result = runner.invoke(app, ["install", "--path", str(tmp_path), "--agent", "antigravity"])
        assert result.exit_code == 0
        assert "installed" in result.output


# ---------------------------------------------------------------------------
# sync with --path
# ---------------------------------------------------------------------------


class TestSyncPathCommand:
    def test_sync_with_path_override(self, tmp_path: Path) -> None:
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            '[tool.shskill]\npath = "SKILLS"\nskills = ["atlas"]\nagent = "gemini"\n',
            encoding="utf-8",
        )
        mock_result = InstallResult(installed=["atlas"])
        with patch("shskills.core.installer.sync_project", return_value=mock_result):
            result = runner.invoke(app, ["sync", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "synced" in result.output

    def test_sync_multi_agent(self, tmp_path: Path) -> None:
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            """
[tool.shskill.claude]
skills = ["interview-prep"]

[tool.shskill.gemini]
skills = ["atlas", "info"]
""",
            encoding="utf-8",
        )
        mock_result = InstallResult(installed=["atlas"])
        with patch("shskills.core.installer.sync_project", return_value=mock_result):
            result = runner.invoke(app, ["sync", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "Syncing agent: claude" in result.output
        assert "Syncing agent: gemini" in result.output

    def test_sync_filtered_agent(self, tmp_path: Path) -> None:
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            """
[tool.shskill.claude]
skills = ["interview-prep"]

[tool.shskill.gemini]
skills = ["atlas", "info"]
""",
            encoding="utf-8",
        )
        mock_result = InstallResult(installed=["interview-prep"])
        with patch("shskills.core.installer.sync_project", return_value=mock_result):
            result = runner.invoke(app, ["sync", "--config", str(config_file), "--agent", "claude"])
        assert result.exit_code == 0
        assert "synced" in result.output

    def test_sync_json_output(self, tmp_path: Path) -> None:
        import json
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text(
            '[tool.shskill]\nskills = ["atlas"]\nagent = "gemini"\n',
            encoding="utf-8",
        )
        mock_result = InstallResult(installed=["atlas"])
        with patch("shskills.core.installer.sync_project", return_value=mock_result):
            result = runner.invoke(app, ["sync", "--config", str(config_file), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "gemini" in data
        assert data["gemini"]["installed"] == ["atlas"]

    def test_doctor_json_output(self) -> None:
        import json
        mock_report = DoctorReport(agent="claude", dest="dummy", installed_count=2, healthy=True)
        with patch("shskills.core.installer.doctor", return_value=mock_report):
            result = runner.invoke(app, ["doctor", "--agent", "claude", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["healthy"] is True
        assert data["installed_count"] == 2
