"""Export existing skills from agent configurations into a generic SKILLS folder."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Sequence
from pathlib import Path

from shskills.config import SKILL_MARKER, resolve_dest
from shskills.core.planner import discover_skills
from shskills.core.validator import compute_skill_sha256
from shskills.exceptions import ConfigError, InstallError
from shskills.models import ExportResult

logger = logging.getLogger(__name__)


def _get_skill_mtime(skill_dir: Path) -> float:
    """Return the newest mtime among all files in *skill_dir*."""
    if not skill_dir.exists():
        return 0.0
    files = [p for p in skill_dir.rglob("*") if p.is_file()]
    if not files:
        return skill_dir.stat().st_mtime
    return max(p.stat().st_mtime for p in files)


def export_skills(
    agent: str = "codex",
    source: Path | str | None = None,
    dest: Path | str = "SKILLS",
    skills: Sequence[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> ExportResult:
    """Read skills from an agent's directory and copy them to a generic destination.

    Checks if a destination skill exists and whether it differs or is newer.
    If destination is newer or content differs, records a conflict unless ``force=True``.

    Args:
        agent:    Agent name whose skills directory to read from (default: ``codex``).
        source:   Override path for the source directory.
        dest:     Target directory for generic skills (default: ``SKILLS``).
        skills:   Optional subset of skill names to export.
        force:    Overwrite existing skills in destination when content differs/is newer.
        dry_run:  Plan without copying any files.
        verbose:  Emit detailed logging.

    Returns:
        ExportResult summarizing what was exported, updated, skipped, or conflicted.
    """
    src_dir = resolve_dest(agent, source)
    dest_dir = Path(dest)

    if not src_dir.exists() or not src_dir.is_dir():
        raise ConfigError(f"Source directory does not exist or is not a directory: {src_dir}")

    # Discover skills in src_dir
    discovered = discover_skills(src_dir)

    if skills:
        requested = set(skills)
        discovered = [s for s in discovered if s.name in requested or s.rel_path in requested]
        found_names = {s.name for s in discovered} | {s.rel_path for s in discovered}
        missing = requested - found_names
        if missing:
            raise InstallError(f"Skill(s) not found in {src_dir}: {', '.join(sorted(missing))}")

    result = ExportResult()

    for skill in discovered:
        target_skill_dir = dest_dir / skill.rel_path
        if not target_skill_dir.exists():
            if not dry_run:
                target_skill_dir.mkdir(parents=True, exist_ok=True)
                for f in skill.files:
                    src_file = skill.local_path / f
                    dst_file = target_skill_dir / f
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_file), str(dst_file))
            result.exported.append(skill.rel_path)
        else:
            # Check if destination content is identical
            dest_marker = target_skill_dir / SKILL_MARKER
            if dest_marker.is_file():
                try:
                    dest_sha = compute_skill_sha256(target_skill_dir, skill.files)
                except Exception:
                    dest_sha = ""
                if dest_sha == skill.content_sha256:
                    result.skipped.append(skill.rel_path)
                    continue

            # Content differs: check modification timestamps
            dest_mtime = _get_skill_mtime(target_skill_dir)
            src_mtime = _get_skill_mtime(skill.local_path)

            if not force:
                result.conflicts.append(skill.rel_path)
                if dest_mtime > src_mtime:
                    logger.warning(
                        "Destination skill '%s' in '%s' is newer than source in '%s'",
                        skill.rel_path,
                        dest_dir,
                        src_dir,
                    )
                else:
                    logger.warning(
                        "Destination skill '%s' in '%s' differs from source in '%s'",
                        skill.rel_path,
                        dest_dir,
                        src_dir,
                    )
                continue

            # Force overwrite
            if not dry_run:
                for f in skill.files:
                    src_file = skill.local_path / f
                    dst_file = target_skill_dir / f
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_file), str(dst_file))
            result.updated.append(skill.rel_path)

    return result
