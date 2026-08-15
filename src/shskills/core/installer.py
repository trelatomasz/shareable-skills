"""Orchestrates the full install lifecycle."""

from __future__ import annotations

import logging
import shutil  # used by execute_plan --clean path
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shskills.project_config import ProjectConfig

from shskills.adapters.base import AgentAdapter
from shskills.config import DEFAULT_REF, resolve_dest
from shskills.core.fetcher import fetch_skills_tree
from shskills.core.manifest import (
    read_manifest,
    remove_manifest_skill,
    update_manifest_skill,
    write_manifest,
)
from shskills.core.exporter import _get_skill_mtime
from shskills.core.planner import discover_skills
from shskills.core.validator import compute_skill_sha256
from shskills.exceptions import ConfigError, InstallError
from shskills.models import (
    DoctorIssue,
    DoctorReport,
    DoctorSeverity,
    InstallAction,
    InstallActionKind,
    InstallPlan,
    InstallResult,
    Manifest,
    SkillInfo,
    SkillSource,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Requested-skill selection
# ---------------------------------------------------------------------------


def _dest_leaf(s: SkillInfo) -> str:
    return Path(s.rel_path).name


def select_requested_skills(
    discovered: list[SkillInfo],
    requested: Sequence[str] | None,
) -> list[SkillInfo]:
    """Filter *discovered* to only those named in *requested*."""
    if not requested:
        return discovered

    selected: list[SkillInfo] = []
    for req in requested:
        req_clean = req.strip().rstrip("/")
        matches = [
            s
            for s in discovered
            if s.name == req_clean
            or s.rel_path == req_clean
            or s.source_rel == req_clean
            or _dest_leaf(s) == req_clean
        ]
        if not matches:
            raise InstallError(f"Requested skill '{req}' not found")

        destination_name = Path(req_clean).name if "/" in req_clean else matches[0].name
        if len(matches) > 1:
            sources = ", ".join(m.source_rel for m in matches)
            raise InstallError(
                f"Skill name '{req}' is ambiguous: {sources}. "
                "Use one of those source paths."
            )
        selected.append(
            matches[0].model_copy(
                update={"name": destination_name, "rel_path": destination_name}
            )
        )
    return selected


# ---------------------------------------------------------------------------
# Plan building
# ---------------------------------------------------------------------------


def _action_for_skill(
    skill: SkillInfo,
    dest_rel: str,
    dest: Path,
    manifest: Manifest | None,
    force: bool,
) -> InstallAction:
    """Determine the InstallAction for a single skill against the destination and manifest."""
    dest_dir = dest / dest_rel

    if manifest is None or dest_rel not in manifest.skills:
        if not dest_dir.exists():
            return InstallAction(
                skill=skill,
                dest_rel=dest_rel,
                kind=InstallActionKind.INSTALL,
            )

    existing = manifest.skills.get(dest_rel) if manifest else None

    # If dest_dir doesn't exist on disk, rely on manifest record
    if not dest_dir.exists():
        if existing and existing.content_sha256 == skill.content_sha256:
            return InstallAction(
                skill=skill,
                dest_rel=dest_rel,
                kind=InstallActionKind.SKIP,
                reason="already up-to-date",
            )
        if force:
            return InstallAction(
                skill=skill,
                dest_rel=dest_rel,
                kind=InstallActionKind.UPDATE,
                reason="hash changed, --force specified",
            )
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.CONFLICT,
            reason="hash changed; use --force to overwrite",
        )

    # dest_dir exists on disk: compute disk sha
    try:
        dest_sha = compute_skill_sha256(dest_dir, skill.files)
    except Exception:
        dest_sha = ""

    # If content on disk is identical to source, it's up to date
    if dest_sha == skill.content_sha256:
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.SKIP,
            reason="already up-to-date",
        )

    if force:
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.UPDATE,
            reason="hash changed, --force specified",
        )

    dest_mtime = _get_skill_mtime(dest_dir)
    src_mtime = _get_skill_mtime(skill.local_path)

    if dest_mtime > src_mtime:
        return InstallAction(
            skill=skill,
            dest_rel=dest_rel,
            kind=InstallActionKind.CONFLICT,
            reason="local changes in agent directory are newer than source (use --force or --export-first)",
        )

    return InstallAction(
        skill=skill,
        dest_rel=dest_rel,
        kind=InstallActionKind.CONFLICT,
        reason="hash changed; use --force to overwrite",
    )


def build_plan(
    skills: list[SkillInfo],
    source: SkillSource,
    agent: str,
    dest: Path,
    manifest: Manifest | None,
    force: bool,
    clean: bool,
    strict: bool,
    dry_run: bool,
) -> InstallPlan:
    """Combine discovered skills + existing manifest into an InstallPlan."""
    actions: list[InstallAction] = []
    for skill in skills:
        action = _action_for_skill(skill, skill.rel_path, dest, manifest, force)
        actions.append(action)

    return InstallPlan(
        source=source,
        agent=agent,
        dest=dest,
        actions=actions,
        dry_run=dry_run,
        force=force,
        clean=clean,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# Plan execution
# ---------------------------------------------------------------------------


def execute_plan(
    plan: InstallPlan,
    manifest: Manifest,
    adapter: AgentAdapter,
    verbose: bool = False,
) -> InstallResult:
    """Execute all actions in *plan*, update *manifest* in-place, return result."""
    result = InstallResult()

    for action in plan.actions:
        skill = action.skill
        dest_dir = plan.dest / action.dest_rel
        dest_path_str = str(plan.dest / action.dest_rel)

        if action.kind == InstallActionKind.SKIP:
            result.skipped.append(action.dest_rel)
            if verbose:
                logger.info("skip  %s (%s)", action.dest_rel, action.reason)
            continue

        if action.kind == InstallActionKind.CONFLICT:
            result.conflicts.append(action.dest_rel)
            logger.warning("conflict %s: %s", action.dest_rel, action.reason)
            continue

        # INSTALL or UPDATE
        if plan.dry_run:
            label = "install" if action.kind == InstallActionKind.INSTALL else "update"
            logger.info("[dry-run] %s  %s", label, action.dest_rel)
            if action.kind == InstallActionKind.INSTALL:
                result.installed.append(action.dest_rel)
            else:
                result.updated.append(action.dest_rel)
            continue

        try:
            adapter.preprocess(skill, dest_dir)
        except OSError as exc:
            result.errors.append(f"{action.dest_rel}: {exc}")
            logger.error("error installing '%s': %s", action.dest_rel, exc)
            continue

        update_manifest_skill(
            manifest,
            dest_rel=action.dest_rel,
            skill_name=skill.name,
            source_path=skill.source_rel,
            dest_path=dest_path_str,
            sha256=skill.content_sha256,
            files=skill.files,
        )

        if action.kind == InstallActionKind.INSTALL:
            result.installed.append(action.dest_rel)
            logger.info("installed %s", action.dest_rel)
        else:
            result.updated.append(action.dest_rel)
            logger.info("updated   %s", action.dest_rel)

    # --clean: remove orphaned skills (in manifest but not in current source)
    if plan.clean and not plan.dry_run:
        installed_keys = {a.dest_rel for a in plan.actions}
        for key in list(manifest.skills.keys()):
            if key not in installed_keys:
                orphan_dir = plan.dest / key
                if orphan_dir.exists():
                    shutil.rmtree(str(orphan_dir))
                remove_manifest_skill(manifest, key)
                result.cleaned.append(key)
                logger.info("cleaned   %s (orphaned)", key)

    return result


# ---------------------------------------------------------------------------
# Public API: install
# ---------------------------------------------------------------------------


def install(
    agent: str,
    url: str | None = None,
    path: str | Path | None = None,
    subpath: str | None = None,
    ref: str = DEFAULT_REF,
    dest: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    clean: bool = False,
    strict: bool = False,
    verbose: bool = False,
    skills: Sequence[str] | None = None,
) -> InstallResult:
    """Fetch and install skills from a remote repository or a local directory.

    Args:
        agent:    Target agent (``antigravity``, ``claude``, ``codex``, ``gemini``,
                  ``opencode``, or ``custom``).
        url:      Git repository URL (if fetching remotely).
        path:     Local path containing skills (if installing locally).
        subpath:  Optional path filter relative to ``SKILLS/`` or the root.
        ref:      Branch, tag, or commit SHA (default: ``main``).
        dest:     Override the default destination directory.
        dry_run:  Plan but do not write any files.
        force:    Overwrite skills whose content has changed.
        clean:    Remove orphaned skills that are no longer in the source.
        strict:   Abort on any conflict instead of warning.
        verbose:  Emit INFO-level log messages for skipped skills too.
        skills:   Optional skill names or source paths to install.

    Returns:
        InstallResult summarising what happened.

    Raises:
        ConfigError:   Invalid agent, missing --dest for custom agent, or neither url nor path.
        FetchError:    Remote repository could not be fetched.
        InstallError:  strict=True and conflicts were detected.
        ManifestError: Manifest could not be read or written.
    """
    from shskills.adapters import get_adapter

    if not url and not path:
        raise ConfigError("Either --url or --path must be provided")

    dest_path = resolve_dest(agent, dest)
    adapter = get_adapter(agent)
    existing_manifest = read_manifest(dest_path)

    if path is not None:
        local_dir = Path(path)
        if not local_dir.exists() or not local_dir.is_dir():
            raise ConfigError(f"Local skills path does not exist or is not a directory: {local_dir}")
        source = SkillSource(path=str(local_dir), ref=ref, subpath=subpath)

        discovered = discover_skills(local_dir, subpath)
        try:
            discovered = select_requested_skills(discovered, skills)
        except InstallError as exc:
            raise InstallError(f"{exc} in '{local_dir}'") from exc

        if not discovered:
            logger.warning("No skills found in '%s'", local_dir)
            return InstallResult()

        plan = build_plan(
            skills=discovered,
            source=source,
            agent=agent,
            dest=dest_path,
            manifest=existing_manifest,
            force=force,
            clean=clean,
            strict=strict,
            dry_run=dry_run,
        )

        conflict_keys = [a.dest_rel for a in plan.actions if a.kind == InstallActionKind.CONFLICT]
        if strict and conflict_keys:
            raise InstallError(
                f"Strict mode: {len(conflict_keys)} conflict(s) detected: "
                + ", ".join(conflict_keys)
            )

        working_manifest: Manifest = existing_manifest or Manifest(
            agent=agent,
            dest=str(dest_path),
            source=source,
        )
        working_manifest.source = source

        result = execute_plan(plan, working_manifest, adapter, verbose=verbose)

        if not dry_run and (result.installed or result.updated or result.cleaned):
            write_manifest(dest_path, working_manifest)

        return result

    assert url is not None
    source = SkillSource(url=url, ref=ref, subpath=subpath)

    with fetch_skills_tree(source) as skills_root:
        discovered = discover_skills(skills_root, source.subpath)

        try:
            discovered = select_requested_skills(discovered, skills)
        except InstallError as exc:
            raise InstallError(f"{exc} in '{url}'") from exc

        if not discovered:
            logger.warning(
                "No skills found at '%s/%s' in '%s'",
                "SKILLS",
                subpath or "",
                url,
            )
            return InstallResult()

        plan = build_plan(
            skills=discovered,
            source=source,
            agent=agent,
            dest=dest_path,
            manifest=existing_manifest,
            force=force,
            clean=clean,
            strict=strict,
            dry_run=dry_run,
        )

        conflict_keys = [a.dest_rel for a in plan.actions if a.kind == InstallActionKind.CONFLICT]
        if strict and conflict_keys:
            raise InstallError(
                f"Strict mode: {len(conflict_keys)} conflict(s) detected: "
                + ", ".join(conflict_keys)
            )

        working_manifest = existing_manifest or Manifest(
            agent=agent,
            dest=str(dest_path),
            source=source,
        )
        working_manifest.source = source

        result = execute_plan(plan, working_manifest, adapter, verbose=verbose)

        if not dry_run and (result.installed or result.updated or result.cleaned):
            write_manifest(dest_path, working_manifest)

    return result


# ---------------------------------------------------------------------------
# Public API: sync_project
# ---------------------------------------------------------------------------


def sync_project(
    project: ProjectConfig,
    dest: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    clean: bool = False,
    strict: bool = False,
    export_first: bool = False,
    verbose: bool = False,
) -> InstallResult:
    """Synchronise all skills declared in *project* across local and remote sources."""
    from shskills.adapters import get_adapter
    from shskills.core.exporter import export_skills
    from shskills.project_config import parse_skill_spec

    dest_path = resolve_dest(project.agent, dest)
    adapter = get_adapter(project.agent)
    existing_manifest = read_manifest(dest_path)

    # If --export-first is requested, export newer local agent modifications to generic source
    if export_first and not dry_run:
        for spec in project.skills:
            src, skill_name = parse_skill_spec(
                spec,
                default_path=project.path,
                default_url=project.url,
                default_ref=project.ref,
            )
            if not src.url and src.path and skill_name:
                agent_skill_dir = dest_path / skill_name
                if agent_skill_dir.is_dir():
                    src_skill_dir = Path(src.path) / skill_name
                    agent_mtime = _get_skill_mtime(agent_skill_dir)
                    src_mtime = _get_skill_mtime(src_skill_dir) if src_skill_dir.exists() else 0.0
                    if agent_mtime > src_mtime:
                        export_skills(
                            agent=project.agent,
                            source=dest_path,
                            dest=src.path,
                            skills=[skill_name],
                            force=True,
                            verbose=verbose,
                        )

    # Parse and group skill specs
    # Key: (is_url, url_or_path, ref, subpath)
    sources_map: dict[tuple[bool, str, str, str | None], list[str] | None] = {}
    for spec in project.skills:
        src, skill_name = parse_skill_spec(
            spec,
            default_path=project.path,
            default_url=project.url,
            default_ref=project.ref,
        )
        is_url = bool(src.url)
        loc = src.url if is_url else (src.path or "SKILLS")
        key = (is_url, loc, src.ref, src.subpath)
        if skill_name is None:
            sources_map[key] = None
        else:
            current = sources_map.get(key)
            if key not in sources_map:
                sources_map[key] = [skill_name]
            elif current is not None:
                current.append(skill_name)

    all_discovered: list[SkillInfo] = []

    with tempfile.TemporaryDirectory(prefix="shskills-sync-") as tmpdir:
        stage_dir = Path(tmpdir)

        # Check if $shskills self-skill was requested
        has_self_skill = False
        for key, req_skills in list(sources_map.items()):
            if req_skills and "$shskills" in req_skills:
                has_self_skill = True
                filtered_req = [r for r in req_skills if r != "$shskills"]
                if filtered_req:
                    sources_map[key] = filtered_req
                else:
                    del sources_map[key]

        if has_self_skill:
            from shskills.self_install import _self_skill_content
            staged_self = stage_dir / "shskills"
            staged_self.mkdir(parents=True, exist_ok=True)
            (staged_self / "SKILL.md").write_text(_self_skill_content(), encoding="utf-8")
            self_discovered = discover_skills(stage_dir)
            all_discovered.extend([s for s in self_discovered if s.name == "shskills"])

        for (is_url, loc, ref, subpath), req_skills in sources_map.items():
            if not is_url:
                local_dir = Path(loc)
                if not local_dir.exists() or not local_dir.is_dir():
                    raise ConfigError(
                        f"Local skills path does not exist or is not a directory: {local_dir}"
                    )
                discovered = discover_skills(local_dir, subpath)
                try:
                    discovered = select_requested_skills(discovered, req_skills)
                except InstallError as exc:
                    raise InstallError(f"{exc} in '{local_dir}'") from exc
                all_discovered.extend(discovered)
            else:
                src = SkillSource(url=loc, ref=ref, subpath=subpath)
                with fetch_skills_tree(src) as skills_root:
                    discovered = discover_skills(skills_root, subpath)
                    try:
                        discovered = select_requested_skills(discovered, req_skills)
                    except InstallError as exc:
                        raise InstallError(f"{exc} in '{loc}'") from exc
                    for s in discovered:
                        staged_path = stage_dir / s.name
                        shutil.copytree(str(s.local_path), str(staged_path), dirs_exist_ok=True)
                        all_discovered.append(s.model_copy(update={"local_path": staged_path}))

        primary_source = SkillSource(path=project.path, url=project.url, ref=project.ref)

        plan = build_plan(
            skills=all_discovered,
            source=primary_source,
            agent=project.agent,
            dest=dest_path,
            manifest=existing_manifest,
            force=force,
            clean=clean,
            strict=strict,
            dry_run=dry_run,
        )

        conflict_keys = [a.dest_rel for a in plan.actions if a.kind == InstallActionKind.CONFLICT]
        if strict and conflict_keys:
            raise InstallError(
                f"Strict mode: {len(conflict_keys)} conflict(s) detected: "
                + ", ".join(conflict_keys)
            )

        working_manifest: Manifest = existing_manifest or Manifest(
            agent=project.agent,
            dest=str(dest_path),
            source=primary_source,
        )
        working_manifest.source = primary_source

        result = execute_plan(plan, working_manifest, adapter, verbose=verbose)

        if not dry_run and (result.installed or result.updated or result.cleaned):
            write_manifest(dest_path, working_manifest)

        return result


# ---------------------------------------------------------------------------
# Public API: uninstall
# ---------------------------------------------------------------------------


def _parse_skill_key(dest_rel: str) -> tuple[str, str]:
    """Split 'prefix__skillname' → (prefix, skillname).

    If there is no ``__`` separator the whole string is treated as the skill
    name and the prefix is an empty string.
    """
    idx = dest_rel.find("__")
    if idx == -1:
        return "", dest_rel
    return dest_rel[:idx], dest_rel[idx + 2 :]


def _key_matches(dest_rel: str, name: str | None, prefix: str | None) -> bool:
    prefix_part, skill_part = _parse_skill_key(dest_rel)
    if name is not None and skill_part != name:
        return False
    return prefix is None or prefix_part.startswith(prefix)


def uninstall(
    agent: str,
    name: str | None = None,
    prefix: str | None = None,
    dest: Path | None = None,
    dry_run: bool = False,
) -> InstallResult:
    """Remove installed skills matching *name* and/or *prefix*.

    Args:
        agent:    Target agent (determines default destination).
        name:     Skill name to match (the part after ``__``).
        prefix:   Prefix filter; matches any installed-skill key whose prefix
                  *starts with* this string.
        dest:     Override the default destination directory.
        dry_run:  Plan without removing any files.

    Returns:
        InstallResult with ``cleaned`` listing removed skills and ``errors``
        listing any I/O failures.

    Raises:
        ConfigError:   Invalid agent or missing --dest for custom agent.
        InstallError:  *name* matches skills under multiple prefixes and
                       *prefix* was not supplied to disambiguate.
        ManifestError: Manifest could not be read or written.
    """
    dest_path = resolve_dest(agent, dest)
    manifest = read_manifest(dest_path)
    if manifest is None:
        return InstallResult()

    matches: dict[str, object] = {
        k: v for k, v in manifest.skills.items() if _key_matches(k, name, prefix)
    }

    if not matches:
        return InstallResult()

    # Ambiguity guard: --name without --prefix must resolve to a single prefix.
    if name is not None and prefix is None:
        unique_prefixes = {_parse_skill_key(k)[0] for k in matches}
        if len(unique_prefixes) > 1:
            raise InstallError(
                f"Name '{name}' is ambiguous — found skills under multiple prefixes: "
                + ", ".join(sorted(unique_prefixes))
                + ". Re-run with --prefix to narrow the selection."
            )

    result = InstallResult()

    for dest_rel in list(matches):
        if dry_run:
            result.cleaned.append(dest_rel)
            continue
        try:
            skill_dir = dest_path / dest_rel
            if skill_dir.exists():
                shutil.rmtree(str(skill_dir))
            remove_manifest_skill(manifest, dest_rel)
            result.cleaned.append(dest_rel)
            logger.info("removed   %s", dest_rel)
        except OSError as exc:
            result.errors.append(f"{dest_rel}: {exc}")
            logger.error("error removing '%s': %s", dest_rel, exc)

    if not dry_run and result.cleaned:
        write_manifest(dest_path, manifest)

    return result


# ---------------------------------------------------------------------------
# Public API: doctor
# ---------------------------------------------------------------------------


def doctor(agent: str, dest: Path | None = None) -> DoctorReport:
    """Check the health of installed skills for *agent*.

    Verifies that:
    - The destination directory exists.
    - The manifest file is readable.
    - Each recorded skill directory is present on disk.
    - Each recorded skill's SHA-256 matches the installed files.

    Returns a DoctorReport with any issues found.
    """
    from shskills.core.validator import compute_skill_sha256, list_skill_files

    dest_path = resolve_dest(agent, dest)
    report = DoctorReport(agent=agent, dest=dest_path)

    if not dest_path.exists():
        report.issues.append(
            DoctorIssue(
                severity=DoctorSeverity.WARNING,
                message=f"Destination directory '{dest_path}' does not exist.",
            )
        )
        return report

    from shskills.core.manifest import read_manifest as _read
    from shskills.exceptions import ManifestError

    try:
        manifest = _read(dest_path)
    except ManifestError as exc:
        report.issues.append(DoctorIssue(severity=DoctorSeverity.ERROR, message=str(exc)))
        return report

    if manifest is None:
        report.issues.append(
            DoctorIssue(
                severity=DoctorSeverity.INFO,
                message="No manifest found. Run 'shskills install' first.",
            )
        )
        return report

    report.installed_count = len(manifest.skills)

    for dest_rel, skill in manifest.skills.items():
        skill_dir = dest_path / dest_rel
        if not skill_dir.exists():
            report.issues.append(
                DoctorIssue(
                    severity=DoctorSeverity.ERROR,
                    message=f"Skill '{dest_rel}' is recorded in manifest but directory is missing.",
                )
            )
            continue

        try:
            actual_files = list_skill_files(skill_dir)
            actual_sha = compute_skill_sha256(skill_dir, actual_files)
        except OSError as exc:
            report.issues.append(
                DoctorIssue(
                    severity=DoctorSeverity.ERROR,
                    message=f"Skill '{dest_rel}': could not read files: {exc}",
                )
            )
            continue

        if actual_sha != skill.content_sha256:
            report.issues.append(
                DoctorIssue(
                    severity=DoctorSeverity.WARNING,
                    message=(
                        f"Skill '{dest_rel}' has been modified locally "
                        f"(expected {skill.content_sha256[:8]}, got {actual_sha[:8]})."
                    ),
                )
            )

    return report
