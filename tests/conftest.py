"""Shared fixtures for the shskills test suite."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Sample SKILL.md content
# ---------------------------------------------------------------------------

SKILL_MD = textwrap.dedent("""\
    ---
    name: {name}
    description: A test skill for {name}
    version: "1.0.0"
    ---

    # {name}

    This is a test skill.
""")


def write_skill(parent: Path, name: str, extra_files: dict[str, str] | None = None) -> Path:
    """Create a valid skill directory under *parent* and return its path."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(SKILL_MD.format(name=name), encoding="utf-8")
    for filename, content in (extra_files or {}).items():
        (skill_dir / filename).write_text(content, encoding="utf-8")
    return skill_dir


# ---------------------------------------------------------------------------
# Single-skill fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_skill_dir(tmp_path: Path) -> Path:
    """A single valid skill directory with a SKILL.md."""
    return write_skill(tmp_path, "test_skill")


# ---------------------------------------------------------------------------
# Multi-skill tree fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_skills_tree(tmp_path: Path) -> Path:
    """A SKILLS/ tree containing two skills in different groups."""
    root = tmp_path / "SKILLS"
    write_skill(root / "common", "welcome_note")
    write_skill(root / "aws", "scale_up")
    return root


# ---------------------------------------------------------------------------
# Local git repository fixture (for integration tests)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def git_skills_repo(tmp_path: Path) -> Path:
    """A local bare-ish git repository with a SKILLS/ tree.

    Branch name is ``main``.  Use ``file://<path>`` as the URL when calling
    the installer.
    """
    repo = tmp_path / "source_repo"
    repo.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    _git(repo, "config", "user.email", "test@shskills.io")
    _git(repo, "config", "user.name", "shskills-test")

    skills = repo / "SKILLS"
    write_skill(skills / "common", "welcome_note")
    write_skill(skills / "aws", "scale_up")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init skills")

    return repo
