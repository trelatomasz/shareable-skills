"""Tests for the no-network self bootstrap."""

from __future__ import annotations

from pathlib import Path

from shskills.config import AGENT_DEST_MAP
from shskills.self_install import install_self


def test_install_self_targets_every_supported_agent(tmp_path: Path) -> None:
    installed = install_self(tmp_path)

    assert len(installed) == len(AGENT_DEST_MAP)
    assert tmp_path / ".claude/skills/shskills/SKILL.md" in installed
    assert tmp_path / ".agents/skills/shskills/SKILL.md" in installed
    assert tmp_path / ".gemini/skills/shskills/SKILL.md" in installed
    assert all(
        path.read_text(encoding="utf-8").startswith("---\nname: shskills") for path in installed
    )


def test_install_self_is_idempotent_and_updates_owned_file(tmp_path: Path) -> None:
    target = install_self(tmp_path, ("claude",))[0]
    target.write_text("stale", encoding="utf-8")

    assert install_self(tmp_path, ("claude",)) == [target]
    assert "shskills" in target.read_text(encoding="utf-8")
