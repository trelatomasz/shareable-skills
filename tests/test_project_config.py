"""Tests for the minimal pyproject.toml configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from shskills.exceptions import ConfigError
from shskills.project_config import ProjectConfig, load_project_config


def test_load_project_config(tmp_path: Path) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.shskill]
url = "https://github.com/example/skills.git"
agent = "codex"
ref = "stable"
skills = ["learning-session", "common/welcome-note"]
""".strip(),
        encoding="utf-8",
    )

    assert load_project_config(config) == ProjectConfig(
        url="https://github.com/example/skills.git",
        agent="codex",
        ref="stable",
        skills=("learning-session", "common/welcome-note"),
    )


@pytest.mark.parametrize(
    "content, message",
    [
        ("[project]\nname = 'empty'", "tool.shskill"),
        ("[tool.shskill]\nskills = ['one']", "url"),
        ("[tool.shskill]\nurl = 'repo'\nskills = []", "skills"),
        ("[tool.shskill]\nurl = 'repo'\nskills = ['one']\nagent = 'custom'", "agent"),
    ],
)
def test_invalid_project_config(tmp_path: Path, content: str, message: str) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_project_config(config)
