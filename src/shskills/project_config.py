"""Read multi-agent and multi-source ``[tool.shskill]`` project configurations."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from shskills.config import DEFAULT_REF, KNOWN_AGENTS
from shskills.exceptions import ConfigError
from shskills.models import SkillSource

_GITHUB_TREE_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/tree/([^/]+)(?:/(.*))?/?$"
)
_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
)


@dataclass(frozen=True)
class ProjectConfig:
    """Skills required by one project for one agent from one or more sources."""

    agent: str
    skills: tuple[str, ...]
    path: str | None = None
    url: str | None = None
    ref: str = DEFAULT_REF


def parse_skill_spec(
    spec: str,
    default_path: str | None = None,
    default_url: str | None = None,
    default_ref: str = DEFAULT_REF,
) -> tuple[SkillSource, str | None]:
    """Parse a skill specification into a (SkillSource, optional_skill_name).

    Supported formats:
    - GitHub tree URL: https://github.com/owner/repo/tree/ref/SKILLS/subpath/
    - GitHub / Git repo URL: https://github.com/owner/repo (assumes default SKILLS/ folder)
    - Self-skill macro: "$shskills", "$shskill", "$self"
    - Plain skill name / local path: "atlas", "info", "common/welcome_note"
    """
    spec_clean = spec.strip()

    # Self-skill macro
    if spec_clean.lower() in ("$shskills", "$shskill", "$self"):
        source = SkillSource(url="https://github.com/trelatomasz/shskills.git", ref=default_ref, subpath=None)
        return source, "$shskills"

    # Match GitHub tree URL
    tree_match = _GITHUB_TREE_RE.match(spec_clean)
    if tree_match:
        owner, repo, ref, raw_subpath = tree_match.groups()
        url = f"https://github.com/{owner}/{repo}.git"
        subpath = None
        if raw_subpath:
            cleaned_subpath = raw_subpath.strip("/")
            if cleaned_subpath == "SKILLS":
                subpath = None
            elif cleaned_subpath.startswith("SKILLS/"):
                subpath = cleaned_subpath[7:].strip("/")
            else:
                subpath = cleaned_subpath
        source = SkillSource(url=url, ref=ref, subpath=subpath)
        return source, None

    # Match GitHub repo URL
    repo_match = _GITHUB_REPO_RE.match(spec_clean)
    if repo_match:
        owner, repo = repo_match.groups()
        url = f"https://github.com/{owner}/{repo}.git"
        source = SkillSource(url=url, ref=default_ref, subpath=None)
        return source, None

    # Match any generic Git / HTTP repo URL
    if spec_clean.startswith(("http://", "https://", "git@")):
        source = SkillSource(url=spec_clean, ref=default_ref, subpath=None)
        return source, None

    # Plain local or configured skill name
    if default_path is not None:
        source = SkillSource(path=default_path, ref=default_ref)
    elif default_url is not None:
        source = SkillSource(url=default_url, ref=default_ref)
    else:
        source = SkillSource(path="SKILLS", ref=default_ref)

    return source, spec_clean


def load_project_configs(path: Path = Path("pyproject.toml")) -> list[ProjectConfig]:
    """Load and validate all agent configurations from [tool.shskill] or [tool.shskills]."""
    if not path.is_file():
        raise ConfigError(f"Project configuration not found: {path}")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        raw = data.get("tool", {}).get("shskill") or data.get("tool", {}).get("shskills")
        if raw is None:
            raise KeyError("Neither [tool.shskill] nor [tool.shskills] found")
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ConfigError(f"Invalid or missing [tool.shskill] in '{path}': {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"[tool.shskill] in '{path}' must be a table")

    # Check for agent sub-tables
    agent_subtables = {
        k: v for k, v in raw.items() if isinstance(v, dict) and k in KNOWN_AGENTS
    }

    if agent_subtables:
        top_url = raw.get("url")
        top_path = raw.get("path")
        top_ref = raw.get("ref", DEFAULT_REF)

        configs: list[ProjectConfig] = []
        for agent_name, agent_raw in agent_subtables.items():
            url = agent_raw.get("url", top_url)
            local_path = agent_raw.get("path", top_path)
            skills = agent_raw.get("skills", [])
            ref = agent_raw.get("ref", top_ref)

            if not isinstance(skills, list) or not skills or not all(
                isinstance(item, str) and item.strip() for item in skills
            ):
                raise ConfigError(
                    f"[tool.shskill.{agent_name}].skills must be a non-empty list of skill names/URLs"
                )

            configs.append(
                ProjectConfig(
                    agent=agent_name,
                    skills=tuple(item.strip() for item in skills),
                    path=local_path.strip() if isinstance(local_path, str) and local_path.strip() else None,
                    url=url.strip() if isinstance(url, str) and url.strip() else None,
                    ref=ref.strip() if isinstance(ref, str) and ref.strip() else DEFAULT_REF,
                )
            )
        return configs

    # Single-table configuration
    url = raw.get("url")
    local_path = raw.get("path")
    skills = raw.get("skills")
    agent = raw.get("agent", "claude")
    ref = raw.get("ref", DEFAULT_REF)

    if not isinstance(skills, list) or not skills or not all(
        isinstance(item, str) and item.strip() for item in skills
    ):
        raise ConfigError("[tool.shskill].skills must be a non-empty list of skill names/URLs")
    if not isinstance(agent, str) or agent not in KNOWN_AGENTS or agent == "custom":
        known = ", ".join(sorted(KNOWN_AGENTS - {"custom"}))
        raise ConfigError(f"[tool.shskill].agent must be one of: {known}")

    return [
        ProjectConfig(
            agent=agent,
            skills=tuple(item.strip() for item in skills),
            path=local_path.strip() if isinstance(local_path, str) and local_path.strip() else None,
            url=url.strip() if isinstance(url, str) and url.strip() else None,
            ref=ref.strip() if isinstance(ref, str) and ref.strip() else DEFAULT_REF,
        )
    ]


def load_project_config(path: Path = Path("pyproject.toml"), agent: str | None = None) -> ProjectConfig:
    """Load a single ProjectConfig for *agent* (or the only defined config)."""
    configs = load_project_configs(path)
    if agent:
        for c in configs:
            if c.agent == agent:
                return c
        raise ConfigError(f"No configuration found for agent '{agent}' in '{path}'")
    return configs[0]
