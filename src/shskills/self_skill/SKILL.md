---
name: shskill
description: Install and synchronize AI-agent skills with the shskill CLI. Use when a user asks to install a skill by name from a Git repository, list available remote skills, sync skills declared by a project, check installed skills, update a skill, or remove a managed skill.
---

# Use shskill

Run commands from the target project's root. Let `shskill` fetch and write skills; do not
copy skill directories manually.

Install one skill when the user gives a repository URL and skill name:

```bash
shskill install <skill-name> --url <repository-url> --agent <agent>
```

This installs the skill in the current project's agent directory, for example
`.claude/skills/<skill-name>/` for Claude.

Use `claude`, `codex`, `gemini`, or `opencode` for `<agent>`. If a name is ambiguous,
inspect the repository and retry with the reported source path:

```bash
shskill list --url <repository-url>
shskill install <group/skill-name> --url <repository-url> --agent <agent>
```

For a repository with `[tool.shskill]` in `pyproject.toml`, install every declared skill:

```bash
shskill sync
```

Use `--dry-run` before a risky update and `--force` only when the user wants to replace a
locally modified managed skill. Verify managed installations with:

```bash
shskill doctor --agent <agent>
```
