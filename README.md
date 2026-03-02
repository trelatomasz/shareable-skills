# shskills

[![CI](https://github.com/trelatomasz/shareable-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/trelatomasz/shareable-skills/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/shskills.svg)](https://pypi.org/project/shskills/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/shskills.svg)](https://pypi.org/project/shskills/)
[![Coverage](https://codecov.io/gh/trelatomasz/shareable-skills/branch/main/graph/badge.svg)](https://codecov.io/gh/trelatomasz/shareable-skills)

**Install agent skills from GitHub repositories.**

`shskills` is a CLI tool and Python library that fetches skill definitions from a remote Git repository and installs them into the correct directory for your AI agent (Claude, Codex, Gemini, OpenCode, or a custom target).

---

## Quickstart

```bash
pip install shskills

# Install all skills for Claude
shskills install --url https://github.com/org/repo --agent claude

# Install a specific group
shskills install --url https://github.com/org/repo --agent claude --subpath aws

# Install a single skill
shskills install --url https://github.com/org/repo --agent claude --subpath aws/scale_up_service
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

## CLI reference

### `install`

Fetch and install skills from a remote repository.

```
shskills install [OPTIONS]

Options:
  --url       -u  TEXT    Git repository URL  [required]
  --agent     -a  TEXT    Target agent: claude, codex, gemini, opencode, custom
  --subpath   -s  TEXT    Path relative to SKILLS/ to install
  --ref       -r  TEXT    Branch, tag, or commit SHA  [default: main]
  --dest      -d  PATH    Override the default destination directory
  --dry-run               Plan without writing any files
  --force     -f          Overwrite skills whose content has changed
  --clean                 Remove orphaned skills no longer in the source
  --strict                Abort on any conflict
  --verbose   -v          Show detailed per-skill progress
```

**Examples:**

```bash
# Install all skills, Claude adapter
shskills install --url https://github.com/org/skills-repo --agent claude

# Preview changes without writing anything
shskills install --url https://github.com/org/skills-repo --agent claude --dry-run

# Force-update all skills even if locally modified
shskills install --url https://github.com/org/skills-repo --agent claude --force

# Pin to a tag
shskills install --url https://github.com/org/skills-repo --agent claude --ref v2.1.0

# Pin to a commit SHA
shskills install \
  --url https://github.com/org/skills-repo \
  --agent claude \
  --ref a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2

# Install into a custom directory
shskills install --url https://github.com/org/skills-repo --agent custom --dest ./my-skills

# Install and remove skills that no longer exist in the source
shskills install --url https://github.com/org/skills-repo --agent claude --clean
```

---

### `list`

List available skills in a remote repository without installing.

```
shskills list --url https://github.com/org/repo [--subpath aws] [--ref main] [--verbose]
```

---

### `installed`

Show skills currently installed for an agent.

```
shskills installed --agent claude
shskills installed --agent claude --dest ./custom-dest
```

---

### `doctor`

Check the health of installed skills: verifies files are present and SHA-256 digests match the manifest.

```
shskills doctor --agent claude
```

Exit code 0 = healthy. Exit code 1 = one or more errors found.

---

## Repository skill format

Skills live in a `SKILLS/` directory tree inside the repository:

```
SKILLS/
  <group>/
    <skill_name>/
      SKILL.md        <- required; marks this as a skill directory
      helper.py       <- optional supporting files
      ...
```

A **skill directory** is any directory containing a `SKILL.md` file.
Nesting depth is unrestricted.

### SKILL.md front-matter

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

## Destination mapping

| `--agent` | Default destination |
|---|---|
| `claude` | `.claude/skills/` |
| `codex` | `.codex/skills/` |
| `gemini` | `.gemini/skills/` |
| `opencode` | `.opencode/skills/` |
| `custom` | **must supply** `--dest` |

The destination path is always relative to the current working directory (your project root).

### Installed path structure

Skills are installed preserving their path relative to the `--subpath` root:

| Invocation | Source path | Installed at |
|---|---|---|
| _(no subpath)_ | `SKILLS/aws/scale_up` | `<dest>/aws/scale_up/` |
| `--subpath aws` | `SKILLS/aws/scale_up` | `<dest>/scale_up/` |
| `--subpath aws/scale_up` | `SKILLS/aws/scale_up` | `<dest>/scale_up/` |

---

## Adapter system

Each agent has an **adapter** (`shskills.adapters.*`) that controls how skill files are written to disk.

The base adapter copies all skill files verbatim. Agent-specific adapters can override
`preprocess(skill, dest_dir)` to rename, reformat, or generate additional files for that
agent's expected format.

```python
from shskills.adapters.base import AgentAdapter
from shskills.models import SkillInfo
from pathlib import Path

class MyAdapter(AgentAdapter):
    @property
    def agent_name(self) -> str:
        return "myagent"

    def preprocess(self, skill: SkillInfo, dest_dir: Path) -> list[str]:
        # Custom transformation: expose only a single prompt.md
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / "prompt.md"
        out.write_text((skill.local_path / "SKILL.md").read_text())
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
    "url": "https://github.com/org/repo",
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

The manifest is used to detect up-to-date skills (idempotency via SHA-256), identify
orphans for `--clean`, and power the `installed` and `doctor` commands.

Written atomically (temp file then rename) so a crash cannot corrupt it.

---

## Python API

```python
from shskills import install, list_skills, installed_skills, doctor
from pathlib import Path

# Install
result = install(
    url="https://github.com/org/repo",
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
skills = list_skills(url="https://github.com/org/repo", subpath="aws")
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

## Conflict policy

| Situation | Default | `--force` | `--clean` |
|---|---|---|---|
| Already installed, same content | Skip (no-op) | Skip | — |
| Already installed, content changed | Warn + skip | Overwrite | — |
| File exists but not in manifest | Warn + skip | Overwrite | — |
| Skill in manifest but not in current source | Keep | Keep | Delete |
| `--strict` mode | Any conflict = fatal | — | — |

---

## Security notes

- **No code execution.** No fetched file is ever executed or evaluated.
- **Path sanitisation.** All source paths are validated against `..` traversal and absolute
  paths; any violation raises an error before any file is touched.
- **Symlinks rejected.** Symlinks inside skill directories are refused.
- **File size cap.** Files larger than 512 KB are rejected (configurable via `MAX_FILE_BYTES`).
- **Untrusted input.** The remote repository is treated as untrusted. SKILL.md front-matter
  is parsed with a plain regex — no YAML or TOML evaluator is invoked.
- **Atomic manifest.** The manifest is written via temp-file-then-rename; a crash cannot
  leave a partial or corrupt manifest file.

---

## Local development

```bash
git clone https://github.com/your-org/shskills
cd shskills

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the CLI
shskills --version

# Lint
ruff check src/ tests/

# Type-check
mypy src/shskills

# Run all tests (unit + integration)
pytest

# Unit tests only (fast, no git required)
pytest tests/ --ignore=tests/integration

# Integration tests only (requires git >= 2.28)
pytest tests/integration/
```

---

## Publishing to PyPI

### One-time setup (OIDC trusted publishing — no token needed)

1. Go to <https://pypi.org/manage/account/publishing/>
2. Add a trusted publisher:
   - **Package name:** `shskills`
   - **Repository:** `your-org/shskills`
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

### Manual publish (fallback)

```bash
uv build
uv publish --token "$PYPI_TOKEN"
```
