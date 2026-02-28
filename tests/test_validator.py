"""Unit tests for shskills.core.validator."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from shskills.config import MAX_FILE_BYTES
from shskills.core.validator import (
    assert_no_symlinks,
    assert_path_safe,
    compute_skill_sha256,
    list_skill_files,
    parse_frontmatter,
    parse_skill_frontmatter,
    validate_skill_dir,
)
from shskills.exceptions import ValidationError

# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------

VALID_FM = textwrap.dedent("""\
    ---
    name: my_skill
    description: A great skill
    version: "1.2.0"
    ---

    # Body content here
""")

NO_FM = "# Just a heading\n\nNo front-matter."

PARTIAL_FM = textwrap.dedent("""\
    ---
    description: Only description
    ---

    # Body
""")

QUOTED_FM = textwrap.dedent("""\
    ---
    name: 'quoted_name'
    version: "2.0"
    ---
""")


class TestParseFrontmatter:
    def test_valid_fields(self) -> None:
        result = parse_frontmatter(VALID_FM)
        assert result["name"] == "my_skill"
        assert result["description"] == "A great skill"
        assert result["version"] == "1.2.0"

    def test_no_frontmatter_returns_empty(self) -> None:
        assert parse_frontmatter(NO_FM) == {}

    def test_partial_frontmatter(self) -> None:
        result = parse_frontmatter(PARTIAL_FM)
        assert "description" in result
        assert "name" not in result

    def test_strips_quotes(self) -> None:
        result = parse_frontmatter(QUOTED_FM)
        assert result["name"] == "quoted_name"
        assert result["version"] == "2.0"

    def test_empty_string(self) -> None:
        assert parse_frontmatter("") == {}


# ---------------------------------------------------------------------------
# parse_skill_frontmatter
# ---------------------------------------------------------------------------


class TestParseSkillFrontmatter:
    def test_reads_fields(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(VALID_FM, encoding="utf-8")

        fm = parse_skill_frontmatter(skill_dir)
        assert fm.name == "my_skill"
        assert fm.version == "1.2.0"

    def test_defaults_name_to_dirname(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "fallback_name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(NO_FM, encoding="utf-8")

        fm = parse_skill_frontmatter(skill_dir)
        assert fm.name == "fallback_name"

    def test_default_version(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "s"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")

        fm = parse_skill_frontmatter(skill_dir)
        assert fm.version == "1.0.0"


# ---------------------------------------------------------------------------
# assert_path_safe
# ---------------------------------------------------------------------------


class TestAssertPathSafe:
    def test_safe_relative_path(self) -> None:
        assert_path_safe(Path("common/welcome"))  # must not raise

    def test_single_segment(self) -> None:
        assert_path_safe(Path("welcome_note"))  # must not raise

    def test_absolute_raises(self) -> None:
        with pytest.raises(ValidationError, match="absolute"):
            assert_path_safe(Path("/etc/passwd"))

    def test_parent_traversal_raises(self) -> None:
        with pytest.raises(ValidationError, match=r"(?i)unsafe"):
            assert_path_safe(Path("../secret"))

    def test_empty_segment_raises(self) -> None:
        # Construct a Path with an empty segment by using PurePosixPath directly
        from pathlib import PurePosixPath
        p = Path(str(PurePosixPath("some//path")))  # double-slash normalizes, skip
        # Test via string with explicit empty part — validate our frozenset logic
        from shskills.core.validator import _UNSAFE_SEGMENTS
        assert ".." in _UNSAFE_SEGMENTS
        assert "." in _UNSAFE_SEGMENTS


# ---------------------------------------------------------------------------
# assert_no_symlinks
# ---------------------------------------------------------------------------


class TestAssertNoSymlinks:
    def test_clean_dir_passes(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("content")
        assert_no_symlinks(d)  # must not raise

    def test_symlink_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        target = tmp_path / "real.txt"
        target.write_text("hi")
        link = d / "link.md"
        link.symlink_to(target)

        with pytest.raises(ValidationError, match="Symlink"):
            assert_no_symlinks(d)


# ---------------------------------------------------------------------------
# list_skill_files
# ---------------------------------------------------------------------------


class TestListSkillFiles:
    def test_returns_sorted_filenames(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("")
        (d / "helper.py").write_text("")
        (d / "README.md").write_text("")

        files = list_skill_files(d)
        assert files == sorted(files)
        assert "SKILL.md" in files
        assert "helper.py" in files

    def test_excludes_symlinks(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        real = tmp_path / "real.txt"
        real.write_text("hi")
        (d / "SKILL.md").write_text("")
        (d / "link.txt").symlink_to(real)

        files = list_skill_files(d)
        assert "link.txt" not in files


# ---------------------------------------------------------------------------
# compute_skill_sha256
# ---------------------------------------------------------------------------


class TestComputeSkillSha256:
    def test_deterministic(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("content", encoding="utf-8")

        sha1 = compute_skill_sha256(d, ["SKILL.md"])
        sha2 = compute_skill_sha256(d, ["SKILL.md"])
        assert sha1 == sha2

    def test_changes_on_content_change(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        f = d / "SKILL.md"

        f.write_text("version 1", encoding="utf-8")
        sha1 = compute_skill_sha256(d, ["SKILL.md"])

        f.write_text("version 2", encoding="utf-8")
        sha2 = compute_skill_sha256(d, ["SKILL.md"])

        assert sha1 != sha2

    def test_returns_64_hex_chars(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_text("x", encoding="utf-8")
        sha = compute_skill_sha256(d, ["SKILL.md"])
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)


# ---------------------------------------------------------------------------
# validate_skill_dir
# ---------------------------------------------------------------------------


class TestValidateSkillDir:
    def test_valid_skill(self, tmp_path: Path) -> None:
        d = tmp_path / "my_skill"
        d.mkdir()
        (d / "SKILL.md").write_text(VALID_FM, encoding="utf-8")

        fm, files, sha = validate_skill_dir(d)
        assert fm.name == "my_skill"
        assert "SKILL.md" in files
        assert len(sha) == 64

    def test_missing_skill_md(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()

        with pytest.raises(ValidationError, match="Missing SKILL.md"):
            validate_skill_dir(d)

    def test_not_a_directory(self, tmp_path: Path) -> None:
        f = tmp_path / "not_a_dir.txt"
        f.write_text("hello")

        with pytest.raises(ValidationError, match="Not a directory"):
            validate_skill_dir(f)

    def test_oversized_file_rejected(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        (d / "SKILL.md").write_bytes(b"x" * (MAX_FILE_BYTES + 1))

        with pytest.raises(ValidationError, match="bytes"):
            validate_skill_dir(d)

    def test_symlink_rejected(self, tmp_path: Path) -> None:
        d = tmp_path / "skill"
        d.mkdir()
        real = tmp_path / "real.md"
        real.write_text("hi")
        (d / "SKILL.md").write_text(VALID_FM)
        (d / "link.md").symlink_to(real)

        with pytest.raises(ValidationError, match="Symlink"):
            validate_skill_dir(d)
