"""Unit tests for shskills.core.exporter."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from shskills.core.exporter import _get_skill_mtime, export_skills
from shskills.exceptions import ConfigError, InstallError


def test_export_skills_success(tmp_path: Path) -> None:
    # Setup source agent directory
    source_dir = tmp_path / ".codex" / "skills"
    skill1_dir = source_dir / "my_skill"
    skill1_dir.mkdir(parents=True)
    (skill1_dir / "SKILL.md").write_text(
        "---\nname: my_skill\ndescription: Test\n---\n# My Skill\n"
    )
    (skill1_dir / "helper.py").write_text("print('hello')\n")

    dest_dir = tmp_path / "SKILLS"

    res = export_skills(agent="codex", source=source_dir, dest=dest_dir)
    assert res.success
    assert res.exported == ["my_skill"]
    assert (dest_dir / "my_skill" / "SKILL.md").is_file()
    assert (dest_dir / "my_skill" / "helper.py").is_file()

    # Re-running without changes skips
    res2 = export_skills(agent="codex", source=source_dir, dest=dest_dir)
    assert res2.skipped == ["my_skill"]


def test_export_skills_conflict_and_force(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex" / "skills"
    skill_dir = source_dir / "skill1"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: skill1\n---\n")

    dest_dir = tmp_path / "SKILLS"
    res1 = export_skills(agent="codex", source=source_dir, dest=dest_dir)
    assert res1.exported == ["skill1"]

    # Modify source
    (skill_dir / "SKILL.md").write_text("---\nname: skill1\ndescription: updated\n---\n")

    # Conflict without force
    res2 = export_skills(agent="codex", source=source_dir, dest=dest_dir, force=False)
    assert res2.conflicts == ["skill1"]

    # With force
    res3 = export_skills(agent="codex", source=source_dir, dest=dest_dir, force=True)
    assert res3.updated == ["skill1"]


def test_export_destination_newer_conflict(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex" / "skills"
    skill_dir = source_dir / "skill1"
    skill_dir.mkdir(parents=True)
    src_file = skill_dir / "SKILL.md"
    src_file.write_text("---\nname: skill1\n---\nold")

    dest_dir = tmp_path / "SKILLS"
    dest_skill = dest_dir / "skill1"
    dest_skill.mkdir(parents=True)
    dest_file = dest_skill / "SKILL.md"
    dest_file.write_text("---\nname: skill1\n---\nnewer generic content")

    # Ensure destination file has a strictly newer mtime
    now = time.time()
    os.utime(src_file, (now - 100, now - 100))
    os.utime(dest_file, (now, now))

    assert _get_skill_mtime(dest_skill) > _get_skill_mtime(skill_dir)

    # Without force: conflicts and does not overwrite
    res = export_skills(agent="codex", source=source_dir, dest=dest_dir, force=False)
    assert res.conflicts == ["skill1"]
    assert "newer generic content" in dest_file.read_text()

    # With force: overwrites
    res_forced = export_skills(agent="codex", source=source_dir, dest=dest_dir, force=True)
    assert res_forced.updated == ["skill1"]
    assert "old" in dest_file.read_text()


def test_export_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        export_skills(agent="codex", source=tmp_path / "nonexistent")


def test_export_missing_requested_skill_raises(tmp_path: Path) -> None:
    source_dir = tmp_path / ".codex" / "skills"
    skill_dir = source_dir / "skill1"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: skill1\n---\n")

    with pytest.raises(InstallError):
        export_skills(agent="codex", source=source_dir, dest=tmp_path / "SKILLS", skills=["skill2"])
