"""OpenAI-compatible tool schema definitions."""

from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the specified path. Returns the file contents as a string with line numbers. Use this to examine existing code before making changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute or relative path to the file to read"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Optional line number to start reading from (1-indexed). If not specified, reads from the beginning."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Optional maximum number of lines to read. If not specified, reads up to 2000 lines."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file at the specified path. This will create the file if it doesn't exist or completely overwrite it if it does. Use read_file first to check existing content before overwriting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete content to write to the file"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing a specific string with new content. The old_string must match exactly (including whitespace and indentation). Use read_file first to see the exact content to replace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to edit"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace. Must be unique within the file unless replace_all is true."
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace old_string with. Can be empty to delete the old_string."
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "If true, replace all occurrences. If false (default), fail if old_string is not unique."
                    }
                },
                "required": ["file_path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory. Returns file and directory names with type indicators.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list. Use '.' for current directory."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "If true, list contents recursively up to 3 levels deep. Default is false."
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter results (e.g., '*.py')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "Find files matching a glob pattern. Returns a list of matching file paths sorted by modification time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files (e.g., '**/*.py' for all Python files, 'src/**/*.tsx' for TSX files in src)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional base directory to search from. Defaults to current directory."
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for a text pattern within files using regex. Returns matching lines with file paths and line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression pattern to search for"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in. Defaults to current directory."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter which files to search (e.g., '*.py')"
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "If true, perform case-insensitive matching. Default is false."
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines to show before and after each match. Default is 0."
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return its output. Use for running tests, builds, git commands, and other CLI operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Directory to run the command in. Defaults to current directory."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds. Default is 120 seconds."
                    }
                },
                "required": ["command"]
            }
        }
    }
]


def get_tools_array() -> list[dict[str, Any]]:
    """Return the tools array for use in API calls."""
    return TOOLS.copy()


def get_tool_names() -> list[str]:
    """Return list of available tool names."""
    return [tool["function"]["name"] for tool in TOOLS]
