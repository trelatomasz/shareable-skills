"""Abstract base class for agent adapters."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from shskills.models import SkillInfo


class AgentAdapter(ABC):
    """Preprocesses and installs a skill into the agent-specific destination.

    Subclasses may override ``preprocess`` to transform skill files for the
    target agent format.  The default implementation copies files verbatim.
    """

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the canonical agent identifier (e.g. ``"claude"``)."""

    def preprocess(self, skill: SkillInfo, dest_dir: Path) -> list[str]:
        """Copy skill files from *skill.local_path* to *dest_dir*.

        May be overridden to rename, reformat, or generate additional files.

        Returns:
            List of filenames that were written inside *dest_dir*.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for rel_path in skill.files:
            src = skill.local_path / rel_path
            dst = dest_dir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            written.append(rel_path)
        return written
