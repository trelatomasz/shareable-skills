"""Install shskills's agent instructions from git for the matching version tag."""

from __future__ import annotations

import logging
from pathlib import Path

from shskills._version import __version__
from shskills.config import AGENT_DEST_MAP
from shskills.core.installer import install
from shskills.exceptions import ConfigError

logger = logging.getLogger(__name__)

DEFAULT_SELF_REPO_URL = "https://github.com/trelatomasz/shskills.git"


def _fallback_local_skills_path() -> Path | None:
    """Return local SKILLS directory if running from repo or tests."""
    candidates = [
        Path(__file__).resolve().parents[2] / "SKILLS",
        Path.cwd() / "SKILLS",
    ]
    for c in candidates:
        if (c / "shskills" / "SKILL.md").is_file():
            return c
    return None


def install_self(
    root: Path,
    agents: tuple[str, ...] | None = None,
    skill_name: str = "shskills",
    repo_url: str = DEFAULT_SELF_REPO_URL,
    ref: str | None = None,
    force: bool = True,
) -> list[Path]:
    """Install the shskills skill from git at matching version tag."""
    selected = agents or tuple(sorted(AGENT_DEST_MAP))
    unknown = sorted(set(selected) - set(AGENT_DEST_MAP))
    if unknown:
        raise ConfigError(f"Unknown agent(s): {', '.join(unknown)}")

    tag_ref = ref or f"v{__version__}"
    local_path = _fallback_local_skills_path()

    installed_files: list[Path] = []
    for agent in selected:
        dest_base = root / AGENT_DEST_MAP[agent]
        dest_base.mkdir(parents=True, exist_ok=True)

        try:
            install(
                agent=agent,
                url=repo_url,
                ref=tag_ref,
                subpath=skill_name,
                dest=dest_base,
                force=force,
            )
        except Exception as exc:
            if local_path is not None:
                logger.debug("Falling back to local SKILLS path %s: %s", local_path, exc)
                install(
                    agent=agent,
                    path=str(local_path),
                    subpath=skill_name,
                    dest=dest_base,
                    force=force,
                )
            else:
                raise

        target_file = dest_base / skill_name / "SKILL.md"
        if target_file.is_file():
            installed_files.append(target_file)

    return installed_files
