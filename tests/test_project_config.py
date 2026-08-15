"""Tests for pyproject.toml configuration and skill spec parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from shskills.exceptions import ConfigError
from shskills.models import SkillSource
from shskills.project_config import (
    ProjectConfig,
    load_project_config,
    load_project_configs,
    parse_skill_spec,
)


def test_load_project_config_single(tmp_path: Path) -> None:
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


def test_load_project_configs_multi_agent(tmp_path: Path) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(
        """
[tool.shskill.claude]
skills = ["interview-prep"]

[tool.shskill.gemini]
path = "SKILLS"
skills = ["atlas", "info"]

[tool.shskill.antigravity]
path = "SKILLS"
skills = [
    "atlas",
    "https://github.com/trelatomasz/shskills/tree/v0.1.4/SKILLS/common/"
]
""".strip(),
        encoding="utf-8",
    )

    configs = load_project_configs(config)
    assert len(configs) == 3
    agent_map = {c.agent: c for c in configs}

    assert agent_map["claude"].skills == ("interview-prep",)
    assert agent_map["gemini"].skills == ("atlas", "info")
    assert agent_map["gemini"].path == "SKILLS"
    assert agent_map["antigravity"].skills == (
        "atlas",
        "https://github.com/trelatomasz/shskills/tree/v0.1.4/SKILLS/common/",
    )

    # Filtered by agent
    assert load_project_config(config, "claude").agent == "claude"
    assert load_project_config(config, "gemini").agent == "gemini"


def test_parse_skill_spec() -> None:
    # GitHub tree with SKILLS/ prefix
    source, name = parse_skill_spec(
        "https://github.com/trelatomasz/shskills/tree/v0.1.4/SKILLS/common/"
    )
    assert source == SkillSource(
        url="https://github.com/trelatomasz/shskills.git",
        ref="v0.1.4",
        subpath="common",
    )
    assert name is None

    # GitHub tree without SKILLS prefix
    source2, name2 = parse_skill_spec("https://github.com/org/repo/tree/main/aws/scale_up")
    assert source2 == SkillSource(
        url="https://github.com/org/repo.git",
        ref="main",
        subpath="aws/scale_up",
    )
    assert name2 is None

    # Plain skill name with default_path
    source3, name3 = parse_skill_spec("atlas", default_path="SKILLS")
    assert source3 == SkillSource(path="SKILLS", ref="main")
    assert name3 == "atlas"

    # Plain repo URL
    source4, name4 = parse_skill_spec("https://github.com/trelatomasz/shskills")
    assert source4 == SkillSource(
        url="https://github.com/trelatomasz/shskills.git",
        ref="main",
        subpath=None,
    )
    assert name4 is None

    # $shskills macro
    source5, name5 = parse_skill_spec("$shskills")
    assert source5 == SkillSource(
        url="https://github.com/trelatomasz/shskills.git",
        ref="main",
        subpath=None,
    )
    assert name5 == "$shskills"


@pytest.mark.parametrize(
    "content, message",
    [
        ("[project]\nname = 'empty'", "Neither"),
        ("[tool.shskill]\nskills = []", "skills"),
        ("[tool.shskill]\nurl = 'repo'\nskills = []", "skills"),
        ("[tool.shskill]\nurl = 'repo'\nskills = ['one']\nagent = 'custom'", "agent"),
    ],
)
def test_invalid_project_config(tmp_path: Path, content: str, message: str) -> None:
    config = tmp_path / "pyproject.toml"
    config.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_project_configs(config)
