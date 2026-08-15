"""Antigravity agent adapter.

Installs skills into ``.agents/skills/``.
"""

from __future__ import annotations

from shskills.adapters.base import AgentAdapter


class AntigravityAdapter(AgentAdapter):
    """Adapter for Google Antigravity."""

    @property
    def agent_name(self) -> str:
        return "antigravity"
