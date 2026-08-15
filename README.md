# shskills

[![CI](https://github.com/trelatomasz/shskills/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/trelatomasz/shskills/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/shskills.svg)](https://pypi.org/project/shskills/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/shskills.svg)](https://pypi.org/project/shskills/)
[![Coverage](https://codecov.io/gh/trelatomasz/shskills/branch/main/graph/badge.svg)](https://codecov.io/gh/trelatomasz/shskills)

**Install agent skills from GitHub repositories.**

`shskills` is a CLI tool and Python library that fetches skill definitions from a remote Git repository or local directory and installs them into the correct directory for your AI agent (Antigravity, Claude, Codex, Gemini, OpenCode, or a custom target).

---

## Quickstart

```bash
pip install shskills

# Teach every supported coding agent in this project how to use shskills
shskills --install self

# Install one skill by name; no SKILLS/ path knowledge required
shskills install learning-session --url https://github.com/org/skills-repo --agent claude

# Install the list declared in pyproject.toml
shskills sync
```

For local development, use an editable source install so changes are visible immediately:

```bash
pip install -e /path/to/shskills
# or add an editable path source with uv in the consuming project
```

---

## Installation

Requires Python >= 3.11 and Git >= 2.28.

```bash
pip install shskills
# or
uv add shskills
# or
pipx install shskills
```

---

## Project Workflow

### Brand-new project setup

Run these commands from your project root:

```bash
# 1. Install shskills
python -m pip install shskills

# 2. Install shskills's own instructions for supported coding agents
shskills --install self
```

Restart the active coding agent after installing the self skill. You can then ask it:

> Install skill `learning-session` from `https://github.com/org/skills-repo`.

The agent will run:

```bash
shskills install learning-session \
  --url https://github.com/org/skills-repo \
  --agent claude
```

Named installation is project-local (e.g. `.claude/skills/learning-session/` or `.agents/skills/learning-session/`); it does not modify a user-global skills directory.

### Project configuration (`pyproject.toml`)

Declare project skill dependencies directly in `pyproject.toml`:

```toml
[tool.shskills]
url = "https://github.com/org/skills-repo.git"
agent = "claude"
skills = ["learning-session", "welcome-note"]
```

Then run `shskills sync`. Add `ref = "v1.2.0"` if you need a pinned branch, tag, or commit SHA.

Multi-agent configuration is also supported:

```toml
[tool.shskills]
url = "https://github.com/org/skills-repo.git"

[tool.shskills.claude]
skills = ["learning-session", "welcome-note"]

[tool.shskills.antigravity]
skills = ["learning-session"]
```

Use this lifecycle after cloning or updating dependencies:

```bash
shskills sync
shskills doctor --agent claude
```

---

## CLI Reference

### `install`

Fetch and install skills from a remote repository or a local directory.

```
shskills install [SKILL_NAME_OR_SOURCE_PATH] [OPTIONS]

Options:
  --url       -u  TEXT    Git repository URL (required if --path is not used)
  --path      -p  PATH    Local directory containing skills (e.g. SKILLS/)
  --agent     -a  TEXT    Target agent: antigravity, claude, codex, gemini, opencode, custom  [default: claude]
  --subpath   -s  TEXT    Path relative to SKILLS/ to install
  --ref       -r  TEXT    Branch, tag, or commit SHA  [default: main]
  --dest      -d  PATH    Override the default destination directory
  --dry-run               Plan without writing any files
  --force     -f          Overwrite skills whose content has changed
  --clean                 Remove orphaned skills no longer in the source
  --strict                Abort on any conflict
  --verbose   -v          Show detailed per-skill progress
```

#### Examples

```bash
# Install a single skill by name
shskills install learning-session --url https://github.com/org/skills-repo --agent claude

# Install all skills from a remote repo
shskills install --url https://github.com/org/skills-repo --agent claude

# Install a specific subpath group
shskills install --url https://github.com/org/skills-repo --agent claude --subpath aws

# Install from a local directory
shskills install --path ./local-skills --agent antigravity

# Preview changes without writing anything
shskills install --url https://github.com/org/skills-repo --agent claude --dry-run

# Force update all skills even if locally modified
shskills install --url https://github.com/org/skills-repo --agent claude --force

# Pin to a tag or commit SHA
shskills install --url https://github.com/org/skills-repo --agent claude --ref v2.1.0

# Install and remove orphaned skills
shskills install --url https://github.com/org/skills-repo --agent claude --clean
```

---

### `export`

Read existing skills from an agent's directory and store them into a generic `SKILLS/` folder:

```bash
# Export all skills from Codex configuration into generic SKILLS/
shskills export --agent codex --dest SKILLS

# Export a single skill with force overwrite
shskills export atlas --agent codex --dest SKILLS --force
```

---

### `--install self`

Install the bundled `shskills` agent instructions into the current project:

```bash
shskills --install self
```

This creates `shskills/SKILL.md` under each supported project-local agent directory: `.agents/skills/`, `.claude/skills/`, `.codex/skills/`, `.gemini/skills/`, and `.opencode/skills/`. Restart active coding agents afterward so they discover the new skill.

---

### `sync`

Read `[tool.shskills]` from `pyproject.toml` and synchronize all listed skills:

```bash
shskills sync
shskills sync --dry-run
shskills sync --force
shskills sync --clean
shskills sync --export-first
```

- `--force`: replaces locally modified managed skills with the remote source.
- `--clean`: removes skills recorded in the manifest that are no longer listed in `pyproject.toml`.
- `--export-first`: writes newer local edits back to the source directory before syncing.

---

### `list`

List available skills in a remote repository without installing:

```bash
shskills list --url https://github.com/org/skills-repo [--subpath aws] [--ref main] [--verbose]
```

---

### `installed`

Show skills currently installed for an agent:

```bash
shskills installed --agent claude
shskills installed --agent claude --dest ./custom-dest
```

---

### `doctor`

Check the health of installed skills: verifies files are present and SHA-256 digests match the manifest:

```bash
shskills doctor --agent claude
```

Exit code 0 = healthy. Exit code 1 = one or more errors found.

---

## Repository Skill Format

Skills live in a `SKILLS/` directory tree inside the repository:

```
SKILLS/
  <group>/
    <skill_name>/
      SKILL.md        <- required; marks this as a skill directory
      helper.py       <- optional supporting files
      ...
```

A **skill directory** is any directory containing a `SKILL.md` file. Nesting depth is unrestricted.

### SKILL.md Front-Matter

`SKILL.md` may begin with an optional `---` delimited front-matter block:

```markdown
---
name: scale_up_service
description: Scales up an ECS service to the desired count
version: "1.2.0"
---

# Scale Up Service

...skill body here...
```

| Field | Required | Default |
|---|---|---|
| `name` | No | directory name |
| `description` | No | `""` |
| `version` | No | `"1.0.0"` |

---

## Destination Mapping

| `--agent` | Default destination |
|---|---|
| `antigravity` | `.agents/skills/` |
| `claude` | `.claude/skills/` |
| `codex` | `.codex/skills/` |
| `gemini` | `.gemini/skills/` |
| `opencode` | `.opencode/skills/` |
| `custom` | **must supply** `--dest` |

The destination path is always relative to the current working directory (your project root).

### Installed Path Structure

Named installs use the skill directory's leaf name. Bulk installs flatten source groups with `__`; `--subpath` makes that source subtree the destination root:

| Invocation | Source path | Installed at |
|---|---|---|
| `install scale_up` | `SKILLS/aws/scale_up` | `<dest>/scale_up/` |
| _(no name or subpath)_ | `SKILLS/aws/scale_up` | `<dest>/aws__scale_up/` |
| `--subpath aws` | `SKILLS/aws/scale_up` | `<dest>/scale_up/` |
| `--subpath aws/scale_up` | `SKILLS/aws/scale_up` | `<dest>/scale_up/` |

---

## Adapter System

Each agent has an **adapter** (`shskills.adapters.*`) that controls how skill files are written to disk.

The base adapter copies all skill files verbatim. Agent-specific adapters can override `preprocess(skill, dest_dir)` to rename, reformat, or generate additional files for that agent's expected format.

```python
from pathlib import Path
from shskills.adapters.base import AgentAdapter
from shskills.models import SkillInfo

class MyAdapter(AgentAdapter):
    @property
    def agent_name(self) -> str:
        return "myagent"

    def preprocess(self, skill: SkillInfo, dest_dir: Path) -> list[str]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / "prompt.md"
        out.write_text((skill.local_path / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")
        return ["prompt.md"]
```

---

## Manifest

After installation, `shskills` writes a manifest at `<dest>/.shskills-manifest.json`:

```json
{
  "version": "1",
  "agent": "claude",
  "dest": ".claude/skills",
  "updated_at": "2026-02-28T12:00:00+00:00",
  "source": {
    "url": "https://github.com/org/skills-repo",
    "ref": "main",
    "subpath": null
  },
  "skills": {
    "aws/scale_up": {
      "name": "scale_up",
      "source_path": "aws/scale_up",
      "dest_path": ".claude/skills/aws/scale_up",
      "content_sha256": "e3b0c44298fc1c149a...",
      "installed_at": "2026-02-28T12:00:00+00:00",
      "files": ["SKILL.md"]
    }
  }
}
```

The manifest detects up-to-date skills (idempotency via SHA-256), identifies orphans for `--clean`, and powers `installed` and `doctor`. It is written atomically via temporary file and replace.

---

## Python API

```python
from pathlib import Path
from shskills import doctor, install, installed_skills, list_skills

# Install skills
result = install(
    url="https://github.com/org/skills-repo",
    agent="claude",
    subpath="aws",
    ref="main",
    dest=Path(".claude/skills"),
    dry_run=False,
    force=False,
    clean=False,
)
print(result.installed)   # ["aws/scale_up"]
print(result.skipped)     # ["aws/other_skill"]

# List remote skills without installing
skills = list_skills(url="https://github.com/org/skills-repo", subpath="aws")
for s in skills:
    print(s.name, s.frontmatter.description)

# List installed skills
for s in installed_skills(agent="claude"):
    print(s.name, s.content_sha256[:8])

# Health check
report = doctor(agent="claude")
print(report.healthy)
for issue in report.issues:
    print(issue.severity, issue.message)
```

---

## Conflict Policy

| Situation | Default | `--force` | `--clean` |
|---|---|---|---|
| Already installed, same content | Skip (no-op) | Skip | — |
| Already installed, content changed | Warn + skip | Overwrite | — |
| File exists but not in manifest | Warn + skip | Overwrite | — |
| Skill in manifest but not in current source | Keep | Keep | Delete |
| `--strict` mode | Any conflict = fatal | — | — |

---

## Security Notes

- **No code execution.** No fetched file is executed or evaluated during discovery or installation.
- **Path sanitisation.** All source paths are validated against `..` traversal and absolute paths before any file is touched.
- **Symlinks rejected.** Symlinks inside skill directories are refused.
- **File size cap.** Files larger than 512 KB are rejected (configurable via `MAX_FILE_BYTES`).
- **Untrusted input.** The remote repository is treated as untrusted. `SKILL.md` front-matter is parsed with a regex rather than executing YAML/TOML code.
- **Atomic manifest.** The manifest is written via temp-file-then-rename; a crash cannot leave a corrupt manifest.

---

## Local Development

```bash
git clone https://github.com/trelatomasz/shskills
cd shskills

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the CLI
shskills --version

# Lint
ruff check src/ tests/

# Type-check
mypy src/shskills

# Run all tests
pytest
```

---

## Publishing to PyPI

### One-time setup (OIDC trusted publishing — no token needed)

1. Go to <https://pypi.org/manage/account/publishing/>
2. Add a trusted publisher:
   - **Package name:** `shskills`
   - **Repository:** `trelatomasz/shskills`
   - **Workflow filename:** `release.yml`

### Release

```bash
# 1. Bump version in src/shskills/_version.py and pyproject.toml
# 2. Commit
git commit -am "chore: bump to v0.2.0"

# 3. Tag and push — the release workflow fires automatically
git tag v0.2.0
git push origin main --tags
```
