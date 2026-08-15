---
name: shskills
description: Install, export, and synchronize AI-agent skills with the shskills CLI. Use when a user asks to install a skill by name from a Git repository or local path, export existing skills to a generic folder, sync skills declared in pyproject.toml, check installed skills, update a skill, or remove a managed skill.
---

# Use shskills

Run commands from the target project's root. Let `shskill` (or `shskills`) fetch, export, and write skills; do not copy skill directories manually.

## 1. Synchronize Project Skills
Synchronize all skills declared in `pyproject.toml` (`[tool.shskill]` or `[tool.shskills]`):

```bash
shskill sync
shskill sync --agent <agent>
shskill sync --export-first   # Export newer agent-side edits to generic skills first
shskill sync --force          # Discard agent-side edits and overwrite with source
```

## 2. Export Skills to Generic Folder
Extract skills from an agent's directory into the generic `SKILLS/` folder:

```bash
shskill export --agent <agent>
shskill export <skill-name> --agent <agent> --dest SKILLS
```

## 3. Install Skills
Install individual skills from a Git repository or local directory:

```bash
shskill install <skill-name> --url <repository-url> --agent <agent>
shskill install <skill-name> --path <local-path> --agent <agent>
```

Supported agents for `<agent>`: `antigravity`, `claude`, `codex`, `gemini`, `opencode`.

## 4. Query and Verify
```bash
shskill list --url <repository-url>
shskill installed --agent <agent>
shskill doctor --agent <agent>
shskill --skill               # Print canonical skill repository URL
```
