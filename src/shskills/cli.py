"""Typer-based CLI for shskills."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from shskills._version import __version__
from shskills.config import DEFAULT_REF, KNOWN_AGENTS
from shskills.exceptions import ConfigError, FetchError, InstallError, ManifestError, ShskillsError

app = typer.Typer(
    name="shskill",
    help="Install agent skills from GitHub repositories or local paths.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

console = Console()
err_console = Console(stderr=True, style="bold red")

# ---------------------------------------------------------------------------
# Shared option types
# ---------------------------------------------------------------------------

_AgentArg = Annotated[
    str,
    typer.Option(
        "--agent",
        "-a",
        help=f"Target agent. One of: {', '.join(sorted(KNOWN_AGENTS))}",
        show_default=True,
    ),
]
_DestArg = Annotated[
    Path | None,
    typer.Option(
        "--dest",
        "-d",
        help="Override the default installation directory.",
    ),
]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s  %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@app.command("export")
def cmd_export(
    skill: Annotated[
        str | None,
        typer.Argument(help="Specific skill name to export. Omit to export all skills."),
    ] = None,
    agent: _AgentArg = "codex",
    source: Annotated[
        Path | None,
        typer.Option("--source", "-s", help="Override the source directory."),
    ] = None,
    dest: Annotated[
        Path,
        typer.Option("--dest", "-d", help="Target directory for generic skills."),
    ] = Path("SKILLS"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan without writing any files."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite skills whose content has changed."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed progress."),
    ] = False,
) -> None:
    """Read existing skills from an agent configuration and store them in a generic SKILLS folder."""
    _setup_logging(verbose)
    from shskills.core.exporter import export_skills
    import json

    try:
        result = export_skills(
            agent=agent,
            source=source,
            dest=dest,
            skills=(skill,) if skill else None,
            force=force,
            dry_run=dry_run,
            verbose=verbose,
        )
    except (ConfigError, InstallError, ManifestError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc
    except ShskillsError as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Unexpected error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        print(json.dumps(result.model_dump(mode="json")))
        if result.errors or result.conflicts:
            raise typer.Exit(code=1)
        return

    prefix = "[dim][dry-run][/dim] " if dry_run else ""

    if result.exported:
        for s in result.exported:
            rprint(f"{prefix}[green]exported[/green]  {s}")
    if result.updated:
        for s in result.updated:
            rprint(f"{prefix}[blue]updated[/blue]   {s}")
    if result.skipped:
        for s in result.skipped:
            rprint(f"{prefix}[dim]skipped[/dim]   {s}")
    if result.conflicts:
        for s in result.conflicts:
            rprint(f"[red]conflict[/red]  {s}  (use --force to overwrite)")
    if result.errors:
        for s in result.errors:
            rprint(f"[bold red]error[/bold red]     {s}")

    total = result.total_changes
    if total == 0 and not result.conflicts and not result.errors:
        rprint("[dim]Nothing to do — all skills up-to-date.[/dim]")
    else:
        summary_parts = []
        if result.exported:
            summary_parts.append(f"[green]{len(result.exported)} exported[/green]")
        if result.updated:
            summary_parts.append(f"[blue]{len(result.updated)} updated[/blue]")
        if result.conflicts:
            summary_parts.append(f"[red]{len(result.conflicts)} conflicts[/red]")
        if result.errors:
            summary_parts.append(f"[bold red]{len(result.errors)} errors[/bold red]")
        rprint("  ".join(summary_parts))

    if result.errors or result.conflicts:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@app.command("install")
def cmd_install(
    url: Annotated[
        str | None,
        typer.Option("--url", "-u", help="Git repository URL."),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Local directory containing skills."),
    ] = None,
    skill: Annotated[
        str | None,
        typer.Argument(help="Skill name or source path. Omit to install all skills."),
    ] = None,
    agent: _AgentArg = "claude",
    subpath: Annotated[
        str | None,
        typer.Option("--subpath", "-s", help="Path relative to SKILLS/ to install."),
    ] = None,
    ref: Annotated[
        str,
        typer.Option("--ref", "-r", help="Branch, tag, or commit SHA."),
    ] = DEFAULT_REF,
    dest: _DestArg = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan without writing any files."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite skills whose content has changed."),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Remove orphaned skills no longer in the source."),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Abort on any conflict."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed progress."),
    ] = False,
) -> None:
    """Fetch and install skills from a remote repository or a local directory."""
    _setup_logging(verbose)
    import json

    if skill == "self" and not url and not path:
        from shskills.self_install import install_self

        installed = install_self(Path.cwd(), agents=(agent,) if agent else None)
        if json_output:
            print(json.dumps({"installed": [str(p) for p in installed]}))
        else:
            for p in installed:
                rprint(f"[green]installed[/green]  {p}")
        return

    if not url and not path:
        if json_output:
            print(json.dumps({"error": "Specify either --url or --path.", "status": "error"}))
        else:
            err_console.print("Error: Specify either --url or --path.")
        raise typer.Exit(code=1)
    if url and path:
        if json_output:
            print(json.dumps({"error": "Specify either --url or --path, not both.", "status": "error"}))
        else:
            err_console.print("Error: Specify either --url or --path, not both.")
        raise typer.Exit(code=1)

    logger = logging.getLogger(__name__)
    logger.debug(
        "install url=%s path=%s agent=%s subpath=%s ref=%s dest=%s dry_run=%s force=%s clean=%s strict=%s",
        url,
        path,
        agent,
        subpath,
        ref,
        dest,
        dry_run,
        force,
        clean,
        strict,
    )

    from shskills.core.installer import install

    try:
        result = install(
            agent=agent,
            url=url,
            path=path,
            subpath=subpath,
            ref=ref,
            dest=dest,
            dry_run=dry_run,
            force=force,
            clean=clean,
            strict=strict,
            verbose=verbose,
            skills=(skill,) if skill else None,
        )
    except (ConfigError, FetchError, InstallError, ManifestError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc
    except ShskillsError as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Unexpected error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        print(json.dumps(result.model_dump(mode="json")))
        if result.errors or (strict and result.conflicts):
            raise typer.Exit(code=1)
        return

    prefix = "[dim][dry-run][/dim] " if dry_run else ""

    if result.installed:
        for s in result.installed:
            rprint(f"{prefix}[green]installed[/green]  {s}")
    if result.updated:
        for s in result.updated:
            rprint(f"{prefix}[blue]updated[/blue]    {s}")
    if result.skipped:
        for s in result.skipped:
            rprint(f"{prefix}[dim]skipped[/dim]    {s}")
    if result.cleaned:
        for s in result.cleaned:
            rprint(f"{prefix}[yellow]cleaned[/yellow]    {s}")
    if result.conflicts:
        for s in result.conflicts:
            rprint(f"[red]conflict[/red]   {s}  (use --force to overwrite)")
    if result.errors:
        for s in result.errors:
            rprint(f"[bold red]error[/bold red]      {s}")

    total = result.total_changes
    if total == 0 and not result.conflicts and not result.errors:
        rprint("[dim]Nothing to do — all skills up-to-date.[/dim]")
    else:
        summary_parts = []
        if result.installed:
            summary_parts.append(f"[green]{len(result.installed)} installed[/green]")
        if result.updated:
            summary_parts.append(f"[blue]{len(result.updated)} updated[/blue]")
        if result.cleaned:
            summary_parts.append(f"[yellow]{len(result.cleaned)} cleaned[/yellow]")
        if result.conflicts:
            summary_parts.append(f"[red]{len(result.conflicts)} conflicts[/red]")
        if result.errors:
            summary_parts.append(f"[bold red]{len(result.errors)} errors[/bold red]")
        rprint("  ".join(summary_parts))

    if result.errors or (strict and result.conflicts):
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


@app.command("sync")
def cmd_sync(
    config: Annotated[
        Path,
        typer.Option("--config", help="pyproject.toml containing [tool.shskill]."),
    ] = Path("pyproject.toml"),
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Override local path containing skills."),
    ] = None,
    agent: Annotated[
        str | None,
        typer.Option("--agent", "-a", help="Override target agent."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan without writing any files."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force sync and overwrite local changes in agent config."),
    ] = False,
    export_first: Annotated[
        bool,
        typer.Option(
            "--export-first",
            help="Export newer local agent changes to generic skills before syncing.",
        ),
    ] = False,
    clean: Annotated[
        bool,
        typer.Option("--clean", help="Remove managed skills not listed in the configuration."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed progress."),
    ] = False,
) -> None:
    """Install the skills declared in [tool.shskill] for all or specified agents."""
    _setup_logging(verbose)
    import json

    from shskills.core.installer import sync_project
    from shskills.project_config import ProjectConfig, load_project_configs

    try:
        all_configs = load_project_configs(config)
        if agent:
            filtered = [c for c in all_configs if c.agent == agent]
            if not filtered:
                raise ConfigError(f"No configuration found for agent '{agent}' in '{config}'")
            target_configs = filtered
        else:
            target_configs = all_configs

        overall_errors = False
        overall_conflicts = False
        results_by_agent: dict[str, dict] = {}

        for project in target_configs:
            if not json_output and len(target_configs) > 1:
                rprint(f"[bold cyan]Syncing agent: {project.agent}[/bold cyan]")

            if path is not None:
                project = ProjectConfig(
                    agent=project.agent,
                    skills=project.skills,
                    path=str(path),
                    url=project.url,
                    ref=project.ref,
                )

            result = sync_project(
                project=project,
                dry_run=dry_run,
                force=force,
                clean=clean,
                export_first=export_first,
                verbose=verbose,
            )

            results_by_agent[project.agent] = result.model_dump(mode="json")

            if not json_output:
                changed = result.installed + result.updated
                for skill_name in changed:
                    rprint(f"[green]synced[/green]  {skill_name}")
                for skill_name in result.skipped:
                    rprint(f"[dim]current[/dim]  {skill_name}")
                for skill_name in result.conflicts:
                    rprint(
                        f"[red]conflict[/red]  {skill_name}  "
                        "(local changes detected; use --force or --export-first)"
                    )
                for skill_name in result.cleaned:
                    rprint(f"[yellow]cleaned[/yellow]  {skill_name}")
                for error in result.errors:
                    rprint(f"[bold red]error[/bold red]  {error}")

                if not result.total_changes and not result.conflicts and not result.errors:
                    rprint(f"[dim]All declared skills for '{project.agent}' are up-to-date.[/dim]")

            if result.errors or result.conflicts:
                overall_errors = True
        
        if json_output:
            print(json.dumps(results_by_agent))

        if overall_errors or overall_conflicts:
            raise typer.Exit(code=1)

    except (ConfigError, FetchError, InstallError, ManifestError, ShskillsError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command("list")
def cmd_list(
    url: Annotated[
        str, typer.Option("--url", "-u", help="Git repository URL.")
    ] = "git@github.com:trelatomasz/shskills.git",
    subpath: Annotated[
        str | None,
        typer.Option("--subpath", "-s", help="Path relative to SKILLS/ to list."),
    ] = None,
    ref: Annotated[
        str,
        typer.Option("--ref", "-r", help="Branch, tag, or commit SHA."),
    ] = DEFAULT_REF,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show front-matter details."),
    ] = False,
) -> None:
    """List available skills in a remote repository."""
    _setup_logging(verbose)
    logger = logging.getLogger(__name__)
    logger.debug("list url=%s subpath=%s ref=%s", url, subpath, ref)
    import json

    from shskills.core.planner import list_skills

    try:
        skills = list_skills(url=url, subpath=subpath, ref=ref)
    except (FetchError, ShskillsError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        skills_data = [
            {
                "name": s.frontmatter.name,
                "rel_path": s.rel_path,
                "version": s.frontmatter.version,
                "description": s.frontmatter.description,
            }
            for s in skills
        ]
        print(json.dumps(skills_data))
        return

    if not skills:
        rprint("[dim]No skills found.[/dim]")
        return

    table = Table(title=f"Skills in {url}", show_lines=False)
    table.add_column("path", style="cyan", no_wrap=True)
    table.add_column("name", style="white")
    table.add_column("version", style="dim")
    if verbose:
        table.add_column("description", style="white")

    for skill in skills:
        row: list[str] = [skill.rel_path, skill.frontmatter.name, skill.frontmatter.version]
        if verbose:
            row.append(skill.frontmatter.description or "—")
        table.add_row(*row)

    console.print(table)


# ---------------------------------------------------------------------------
# installed
# ---------------------------------------------------------------------------


@app.command("installed")
def cmd_installed(
    agent: _AgentArg = "claude",
    dest: _DestArg = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
) -> None:
    """List skills that are currently installed for an agent."""
    logger = logging.getLogger(__name__)
    logger.debug("installed agent=%s dest=%s", agent, dest)
    import json
    from shskills.core.manifest import installed_skills

    try:
        skills = installed_skills(agent=agent, dest=dest)
    except (ConfigError, ManifestError, ShskillsError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        skills_data = [
            {
                "dest_path": s.dest_path,
                "name": s.name,
                "content_sha256": s.content_sha256,
                "installed_at": s.installed_at.isoformat(),
            }
            for s in skills
        ]
        print(json.dumps(skills_data))
        return

    if not skills:
        rprint(f"[dim]No skills installed for agent '{agent}'.[/dim]")
        return

    table = Table(title=f"Installed skills — {agent}", show_lines=False)
    table.add_column("dest path", style="cyan", no_wrap=True)
    table.add_column("name", style="white")
    table.add_column("sha256", style="dim")
    table.add_column("installed", style="dim")

    for skill in skills:
        table.add_row(
            skill.dest_path,
            skill.name,
            skill.content_sha256[:12] + "…",
            skill.installed_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command("doctor")
def cmd_doctor(
    agent: _AgentArg = "claude",
    dest: _DestArg = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
) -> None:
    """Check the health of installed skills for an agent."""
    logger = logging.getLogger(__name__)
    logger.debug("doctor agent=%s dest=%s", agent, dest)
    import json
    from shskills.core.installer import doctor
    from shskills.models import DoctorSeverity

    try:
        report = doctor(agent=agent, dest=dest)
    except (ConfigError, ShskillsError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        print(json.dumps(report.model_dump(mode="json")))
        if not report.healthy:
            raise typer.Exit(code=1)
        return

    rprint(f"Agent:  [bold]{report.agent}[/bold]")
    rprint(f"Dest:   [bold]{report.dest}[/bold]")
    rprint(f"Skills: [bold]{report.installed_count}[/bold] installed\n")

    if not report.issues:
        rprint("[green]All good.[/green]")
        return

    severity_color = {
        DoctorSeverity.ERROR: "bold red",
        DoctorSeverity.WARNING: "yellow",
        DoctorSeverity.INFO: "dim",
    }

    for issue in report.issues:
        color = severity_color[issue.severity]
        rprint(f"[{color}]{issue.severity.value.upper():8s}[/{color}]  {issue.message}")

    if not report.healthy:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


@app.command("uninstall")
def cmd_uninstall(
    agent: _AgentArg = "claude",
    dest: _DestArg = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="Skill name to remove (part after '__')."),
    ] = None,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help="Remove all skills whose prefix starts with this value.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan without removing any files."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help="Output machine-readable JSON."),
    ] = False,
) -> None:
    """Remove installed skills by name and/or prefix.

    Skill keys follow the format ``<prefix>__<skillname>``.  You may filter
    by either part independently or combine both flags.

    When --name is given without --prefix and multiple prefixes own a skill
    with that name the command fails and asks you to add --prefix.
    """
    import json

    if name is None and prefix is None:
        if json_output:
            print(json.dumps({"error": "Specify at least --name or --prefix.", "status": "error"}))
        else:
            err_console.print("Error: specify at least --name or --prefix.")
        raise typer.Exit(code=1)

    from shskills.core.installer import uninstall

    try:
        result = uninstall(
            agent=agent,
            name=name,
            prefix=prefix,
            dest=dest,
            dry_run=dry_run,
        )
    except (ConfigError, InstallError, ManifestError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Error: {exc}")
        raise typer.Exit(code=1) from exc
    except ShskillsError as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "status": "error"}))
        else:
            err_console.print(f"Unexpected error: {exc}")
        raise typer.Exit(code=1) from exc

    if json_output:
        print(json.dumps(result.model_dump(mode="json")))
        if result.errors:
            raise typer.Exit(code=1)
        return

    pfix = "[dim][dry-run][/dim] " if dry_run else ""

    if not result.cleaned and not result.errors:
        rprint("[dim]No matching skills found.[/dim]")
        return

    for s in result.cleaned:
        rprint(f"{pfix}[yellow]removed[/yellow]    {s}")
    for s in result.errors:
        rprint(f"[bold red]error[/bold red]      {s}")

    if result.cleaned:
        rprint(f"[yellow]{len(result.cleaned)} removed[/yellow]")

    if result.errors:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def _version_callback(
    install_target: Annotated[
        str | None,
        typer.Option("--install", help="Install a bundled component (currently: self)."),
    ] = None,
    skill_link: Annotated[
        bool,
        typer.Option("--skill", help="Print canonical skill repository URL and exit.", is_eager=True),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Print version and exit.", is_eager=True),
    ] = False,
) -> None:
    if skill_link:
        print("https://github.com/trelatomasz/shskills")
        raise typer.Exit()
    if install_target is not None:
        if install_target != "self":
            err_console.print("Error: --install currently accepts only 'self'.")
            raise typer.Exit(code=1)
        from shskills.self_install import install_self

        for path in install_self(Path.cwd()):
            rprint(f"[green]installed[/green]  {path}")
        rprint("[dim]Restart active coding agents so they discover the new skill.[/dim]")
        raise typer.Exit()
    if version:
        rprint(f"shskill {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
