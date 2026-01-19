"""Tool executor - implements actual file and command operations."""

import fnmatch
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


class ToolExecutor:
    """Executes tool calls and returns results."""

    def __init__(
        self,
        working_directory: str | None = None,
        allowed_directories: list[str] | None = None,
        allow_commands: bool = True,
        command_allowlist: list[str] | None = None,
    ):
        """
        Initialize the tool executor.

        Args:
            working_directory: Base directory for file operations. Defaults to cwd.
            allowed_directories: List of directories that can be accessed. If None, only working_directory.
            allow_commands: Whether to allow run_command tool. Default True.
            command_allowlist: If set, only these command prefixes are allowed.
        """
        self.working_directory = Path(working_directory or os.getcwd()).resolve()
        self.allowed_directories = [
            Path(d).resolve() for d in (allowed_directories or [str(self.working_directory)])
        ]
        self.allow_commands = allow_commands
        self.command_allowlist = command_allowlist

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a path relative to working directory and validate access."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.working_directory / path
        path = path.resolve()

        # Security check: ensure path is within allowed directories
        if not any(self._is_subpath(path, allowed) for allowed in self.allowed_directories):
            raise PermissionError(
                f"Access denied: {path} is outside allowed directories"
            )
        return path

    def _is_subpath(self, path: Path, parent: Path) -> bool:
        """Check if path is equal to or a subpath of parent."""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a tool call and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            String result to return to the LLM
        """
        try:
            method = getattr(self, f"_tool_{tool_name}", None)
            if method is None:
                return f"Error: Unknown tool '{tool_name}'"
            return method(**arguments)
        except PermissionError as e:
            return f"Permission denied: {e}"
        except FileNotFoundError as e:
            return f"File not found: {e}"
        except Exception as e:
            return f"Error executing {tool_name}: {type(e).__name__}: {e}"

    def execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool call from the API response format.

        Args:
            tool_call: Tool call object from API response with 'function' and 'id'

        Returns:
            Tool result message in API format
        """
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        arguments_str = function.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError:
            arguments = {}

        result = self.execute(tool_name, arguments)

        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "content": result
        }

    # ========== Tool Implementations ==========

    def _tool_read_file(
        self,
        file_path: str,
        offset: int | None = None,
        limit: int | None = None
    ) -> str:
        """Read file contents with optional offset and limit."""
        path = self._resolve_path(file_path)

        if not path.exists():
            return f"Error: File does not exist: {file_path}"

        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading file: {e}"

        # Apply offset (1-indexed)
        start_line = (offset or 1) - 1
        if start_line < 0:
            start_line = 0

        # Apply limit
        max_lines = limit or 2000
        end_line = start_line + max_lines

        selected_lines = lines[start_line:end_line]

        # Format with line numbers
        output_lines = []
        for i, line in enumerate(selected_lines, start=start_line + 1):
            # Truncate very long lines
            if len(line) > 2000:
                line = line[:2000] + "...[truncated]\n"
            output_lines.append(f"{i:6}\t{line.rstrip()}")

        if not output_lines:
            return f"File is empty or offset is beyond file length: {file_path}"

        result = "\n".join(output_lines)

        # Add info about truncation
        if end_line < len(lines):
            result += f"\n\n[Showing lines {start_line + 1}-{end_line} of {len(lines)} total]"

        return result

    def _tool_write_file(self, file_path: str, content: str) -> str:
        """Write content to a file."""
        path = self._resolve_path(file_path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote {len(content)} bytes to {file_path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _tool_edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> str:
        """Edit file by string replacement."""
        path = self._resolve_path(file_path)

        if not path.exists():
            return f"Error: File does not exist: {file_path}"

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

        # Check if old_string exists
        count = content.count(old_string)
        if count == 0:
            return f"Error: old_string not found in file. Make sure it matches exactly including whitespace."

        if count > 1 and not replace_all:
            return f"Error: old_string found {count} times in file. Set replace_all=true to replace all, or provide more context to make it unique."

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced_count = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replaced_count = 1

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully replaced {replaced_count} occurrence(s) in {file_path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _tool_list_directory(
        self,
        path: str,
        recursive: bool = False,
        pattern: str | None = None
    ) -> str:
        """List directory contents."""
        dir_path = self._resolve_path(path)

        if not dir_path.exists():
            return f"Error: Directory does not exist: {path}"

        if not dir_path.is_dir():
            return f"Error: Path is not a directory: {path}"

        results = []

        if recursive:
            for root, dirs, files in os.walk(dir_path):
                # Limit depth to 3 levels
                depth = len(Path(root).relative_to(dir_path).parts)
                if depth > 3:
                    dirs.clear()
                    continue

                rel_root = Path(root).relative_to(dir_path)

                for d in sorted(dirs):
                    rel_path = rel_root / d if str(rel_root) != "." else Path(d)
                    if pattern is None or fnmatch.fnmatch(str(rel_path), pattern):
                        results.append(f"[DIR]  {rel_path}/")

                for f in sorted(files):
                    rel_path = rel_root / f if str(rel_root) != "." else Path(f)
                    if pattern is None or fnmatch.fnmatch(str(rel_path), pattern):
                        results.append(f"[FILE] {rel_path}")
        else:
            entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
            for entry in entries:
                if pattern and not fnmatch.fnmatch(entry.name, pattern):
                    continue
                if entry.is_dir():
                    results.append(f"[DIR]  {entry.name}/")
                else:
                    results.append(f"[FILE] {entry.name}")

        if not results:
            return f"Directory is empty or no files match pattern: {path}"

        return "\n".join(results[:500])  # Limit output

    def _tool_glob_files(self, pattern: str, path: str | None = None) -> str:
        """Find files matching a glob pattern."""
        base_path = self._resolve_path(path or ".")

        if not base_path.is_dir():
            return f"Error: Path is not a directory: {path}"

        matches = list(base_path.glob(pattern))

        # Sort by modification time (most recent first)
        matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        if not matches:
            return f"No files found matching pattern: {pattern}"

        # Format results with relative paths
        results = []
        for match in matches[:200]:  # Limit results
            try:
                rel_path = match.relative_to(base_path)
                results.append(str(rel_path))
            except ValueError:
                results.append(str(match))

        output = "\n".join(results)
        if len(matches) > 200:
            output += f"\n\n[Showing 200 of {len(matches)} matches]"

        return output

    def _tool_grep_search(
        self,
        pattern: str,
        path: str | None = None,
        file_pattern: str | None = None,
        case_insensitive: bool = False,
        context_lines: int = 0
    ) -> str:
        """Search for pattern in files."""
        search_path = self._resolve_path(path or ".")

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"Invalid regex pattern: {e}"

        results = []
        files_searched = 0
        matches_found = 0

        # Collect files to search
        if search_path.is_file():
            files_to_search = [search_path]
        else:
            if file_pattern:
                files_to_search = list(search_path.glob(f"**/{file_pattern}"))
            else:
                files_to_search = [f for f in search_path.rglob("*") if f.is_file()]

        # Filter out binary files and limit
        text_files = []
        for f in files_to_search[:1000]:
            try:
                # Quick binary check
                with open(f, "rb") as fp:
                    chunk = fp.read(1024)
                    if b"\x00" in chunk:
                        continue
                text_files.append(f)
            except Exception:
                continue

        for file_path in text_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                files_searched += 1

                for i, line in enumerate(lines):
                    if regex.search(line):
                        matches_found += 1

                        # Get context
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)

                        try:
                            rel_path = file_path.relative_to(search_path)
                        except ValueError:
                            rel_path = file_path

                        if context_lines > 0:
                            results.append(f"\n{rel_path}:")
                            for j in range(start, end):
                                prefix = ">" if j == i else " "
                                results.append(f"{prefix} {j + 1}: {lines[j].rstrip()}")
                        else:
                            results.append(f"{rel_path}:{i + 1}: {line.rstrip()}")

                        if matches_found >= 100:
                            break

            except Exception:
                continue

            if matches_found >= 100:
                break

        if not results:
            return f"No matches found for pattern: {pattern}"

        output = "\n".join(results)
        output += f"\n\n[Found {matches_found} matches in {files_searched} files searched]"

        return output

    def _tool_run_command(
        self,
        command: str,
        working_directory: str | None = None,
        timeout: int = 120
    ) -> str:
        """Execute a shell command."""
        if not self.allow_commands:
            return "Error: Command execution is disabled"

        # Check command allowlist
        if self.command_allowlist:
            allowed = any(command.strip().startswith(prefix) for prefix in self.command_allowlist)
            if not allowed:
                return f"Error: Command not in allowlist. Allowed prefixes: {self.command_allowlist}"

        cwd = self._resolve_path(working_directory) if working_directory else self.working_directory

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=min(timeout, 600)  # Cap at 10 minutes
            )

            output_parts = []
            if result.stdout:
                output_parts.append(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                output_parts.append(f"STDERR:\n{result.stderr}")

            output = "\n\n".join(output_parts) if output_parts else "(no output)"

            # Truncate if too long
            if len(output) > 30000:
                output = output[:30000] + "\n\n[Output truncated at 30000 characters]"

            status = "Success" if result.returncode == 0 else f"Failed (exit code {result.returncode})"
            return f"{status}\n\n{output}"

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds"
        except Exception as e:
            return f"Error executing command: {e}"
