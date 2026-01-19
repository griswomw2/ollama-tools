"""Tests for the ToolExecutor."""

import os
import tempfile
from pathlib import Path

import pytest

from ollama_tools.executor import ToolExecutor


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def executor(temp_dir):
    """Create a ToolExecutor with temp directory."""
    return ToolExecutor(
        working_directory=str(temp_dir),
        allow_commands=True,
        command_allowlist=["echo", "ls", "cat"]
    )


class TestReadFile:
    def test_read_existing_file(self, executor, temp_dir):
        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3\n")

        result = executor.execute("read_file", {"file_path": "test.txt"})

        assert "line 1" in result
        assert "line 2" in result
        assert "line 3" in result

    def test_read_nonexistent_file(self, executor):
        result = executor.execute("read_file", {"file_path": "nonexistent.txt"})
        assert "does not exist" in result.lower() or "not found" in result.lower()

    def test_read_with_offset_and_limit(self, executor, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("\n".join(f"line {i}" for i in range(1, 11)))

        result = executor.execute("read_file", {
            "file_path": "test.txt",
            "offset": 3,
            "limit": 2
        })

        assert "line 3" in result
        assert "line 4" in result
        assert "line 5" not in result


class TestWriteFile:
    def test_write_new_file(self, executor, temp_dir):
        result = executor.execute("write_file", {
            "file_path": "new_file.txt",
            "content": "Hello, World!"
        })

        assert "success" in result.lower()
        assert (temp_dir / "new_file.txt").read_text() == "Hello, World!"

    def test_write_creates_directories(self, executor, temp_dir):
        result = executor.execute("write_file", {
            "file_path": "subdir/nested/file.txt",
            "content": "nested content"
        })

        assert "success" in result.lower()
        assert (temp_dir / "subdir/nested/file.txt").read_text() == "nested content"


class TestEditFile:
    def test_edit_replace_unique_string(self, executor, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        result = executor.execute("edit_file", {
            "file_path": "test.txt",
            "old_string": "World",
            "new_string": "Universe"
        })

        assert "success" in result.lower()
        assert test_file.read_text() == "Hello, Universe!"

    def test_edit_nonunique_string_fails(self, executor, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("foo bar foo")

        result = executor.execute("edit_file", {
            "file_path": "test.txt",
            "old_string": "foo",
            "new_string": "baz"
        })

        assert "2 times" in result.lower() or "not unique" in result.lower()

    def test_edit_replace_all(self, executor, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("foo bar foo")

        result = executor.execute("edit_file", {
            "file_path": "test.txt",
            "old_string": "foo",
            "new_string": "baz",
            "replace_all": True
        })

        assert "success" in result.lower()
        assert test_file.read_text() == "baz bar baz"


class TestListDirectory:
    def test_list_directory(self, executor, temp_dir):
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.py").touch()
        (temp_dir / "subdir").mkdir()

        result = executor.execute("list_directory", {"path": "."})

        assert "file1.txt" in result
        assert "file2.py" in result
        assert "subdir" in result

    def test_list_with_pattern(self, executor, temp_dir):
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.py").touch()

        result = executor.execute("list_directory", {
            "path": ".",
            "pattern": "*.py"
        })

        assert "file2.py" in result
        assert "file1.txt" not in result


class TestGlobFiles:
    def test_glob_pattern(self, executor, temp_dir):
        (temp_dir / "src").mkdir()
        (temp_dir / "src/main.py").touch()
        (temp_dir / "src/utils.py").touch()
        (temp_dir / "readme.md").touch()

        result = executor.execute("glob_files", {"pattern": "**/*.py"})

        assert "main.py" in result
        assert "utils.py" in result
        assert "readme.md" not in result


class TestGrepSearch:
    def test_grep_finds_pattern(self, executor, temp_dir):
        test_file = temp_dir / "test.py"
        test_file.write_text("def hello():\n    print('world')\n")

        result = executor.execute("grep_search", {"pattern": "def.*hello"})

        assert "test.py" in result
        assert "hello" in result

    def test_grep_case_insensitive(self, executor, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello World\n")

        result = executor.execute("grep_search", {
            "pattern": "hello",
            "case_insensitive": True
        })

        assert "Hello" in result


class TestRunCommand:
    def test_run_allowed_command(self, executor):
        result = executor.execute("run_command", {"command": "echo 'hello'"})
        assert "hello" in result

    def test_run_disallowed_command(self, executor):
        result = executor.execute("run_command", {"command": "rm -rf /"})
        assert "not in allowlist" in result.lower()


class TestSecurityRestrictions:
    def test_cannot_access_outside_working_dir(self, temp_dir):
        executor = ToolExecutor(
            working_directory=str(temp_dir),
            allowed_directories=[str(temp_dir)]
        )

        result = executor.execute("read_file", {"file_path": "/etc/passwd"})
        assert "denied" in result.lower() or "outside" in result.lower()

    def test_commands_can_be_disabled(self, temp_dir):
        executor = ToolExecutor(
            working_directory=str(temp_dir),
            allow_commands=False
        )

        result = executor.execute("run_command", {"command": "echo test"})
        assert "disabled" in result.lower()
