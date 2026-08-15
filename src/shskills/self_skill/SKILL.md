---
name: shskills
description: Install, export, and synchronize AI-agent skills with the shskills CLI. Use when a user asks to install a skill by name from a Git repository or local path, export existing skills to a generic folder, sync skills declared in pyproject.toml, check installed skills, update a skill, or remove a managed skill.
---

# Use shskills

Run commands from the target project's root. Let `shskills` fetch, export, and write skills; do not copy skill directories manually.

## 1. Synchronize Project Skills
Synchronize all skills declared in `pyproject.toml` (`[tool.shskills]`):

```bash
shskills sync
shskills sync --agent <agent>
shskills sync --export-first   # Export newer agent-side edits to generic skills first
shskills sync --force          # Discard agent-side edits and overwrite with source
```

## 2. Export Skills to Generic Folder
Extract skills from an agent's directory into the generic `SKILLS/` folder:

```bash
shskills export --agent <agent>
shskills export <skill-name> --agent <agent> --dest SKILLS
```

## 3. Install Skills
Install individual skills from a Git repository or local directory:

```bash
shskills install <skill-name> --url <repository-url> --agent <agent>
shskills install <skill-name> --path <local-path> --agent <agent>
```

Supported agents for `<agent>`: `antigravity`, `claude`, `codex`, `gemini`, `opencode`.

## 4. Query and Verify
```bash
shskills list --url <repository-url>
shskills installed --agent <agent>
shskills doctor --agent <agent>
shskills --skill               # Print canonical skill repository URL
```
