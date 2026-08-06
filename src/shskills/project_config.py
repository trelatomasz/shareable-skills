"""Read the intentionally small ``[tool.shskill]`` project configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from shskills.config import DEFAULT_REF, KNOWN_AGENTS
from shskills.exceptions import ConfigError


@dataclass(frozen=True)
class ProjectConfig:
    """Skills required by one project from one repository."""

    url: str
    skills: tuple[str, ...]
    agent: str = "claude"
    ref: str = DEFAULT_REF


def load_project_config(path: Path = Path("pyproject.toml")) -> ProjectConfig:
    """Load and validate ``[tool.shskill]`` from *path*."""
    if not path.is_file():
        raise ConfigError(f"Project configuration not found: {path}")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        raw = data["tool"]["shskill"]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ConfigError(f"Invalid or missing [tool.shskill] in '{path}': {exc}") from exc

    url = raw.get("url")
    skills = raw.get("skills")
    agent = raw.get("agent", "claude")
    ref = raw.get("ref", DEFAULT_REF)

    if not isinstance(url, str) or not url.strip():
        raise ConfigError("[tool.shskill].url must be a non-empty string")
    if not isinstance(skills, list) or not skills or not all(
        isinstance(item, str) and item.strip() for item in skills
    ):
        raise ConfigError("[tool.shskill].skills must be a non-empty list of skill names")
    if not isinstance(agent, str) or agent not in KNOWN_AGENTS or agent == "custom":
        known = ", ".join(sorted(KNOWN_AGENTS - {"custom"}))
        raise ConfigError(f"[tool.shskill].agent must be one of: {known}")
    if not isinstance(ref, str) or not ref.strip():
        raise ConfigError("[tool.shskill].ref must be a non-empty string")

    return ProjectConfig(
        url=url.strip(),
        skills=tuple(item.strip() for item in skills),
        agent=agent,
        ref=ref.strip(),
    )
