"""Install shskill's bundled agent instructions into the current project."""

from __future__ import annotations

import os
import tempfile
from importlib.resources import files
from pathlib import Path

from shskills.config import AGENT_DEST_MAP
from shskills.exceptions import ConfigError


def _self_skill_content() -> str:
    resource = files("shskills").joinpath("self_skill", "SKILL.md")
    return resource.read_text(encoding="utf-8")


def install_self(
    root: Path,
    agents: tuple[str, ...] | None = None,
    skill_name: str = "shskills",
) -> list[Path]:
    """Install the bundled shskills skill for selected agents, or all known agents."""
    selected = agents or tuple(sorted(AGENT_DEST_MAP))
    unknown = sorted(set(selected) - set(AGENT_DEST_MAP))
    if unknown:
        raise ConfigError(f"Unknown agent(s): {', '.join(unknown)}")

    content = _self_skill_content()
    installed: list[Path] = []
    for agent in selected:
        dest_base = root / AGENT_DEST_MAP[agent]
        dest_base.mkdir(parents=True, exist_ok=True)
        skill_dir = dest_base / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        target = skill_dir / "SKILL.md"
        fd, temporary = tempfile.mkstemp(prefix=".SKILL-", suffix=".tmp", dir=skill_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            os.replace(temporary, target)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
        installed.append(target)
    return installed
