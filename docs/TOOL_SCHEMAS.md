# OpenAI-Compatible Tool Schemas for Devstral-Small

This document defines tool schemas in OpenAI-compatible JSON format for use with devstral-small-2:24b served through Ollama. These tools enable effective file operations within a repository.

## Implementation Available

A complete implementation of these tools is available in this repository. See the [README](../README.md) for installation and usage instructions.

```bash
# Quick start
pip install -e .
ollama-tools-proxy --working-dir /path/to/project
```

## Overview

Devstral models support both Mistral function calling and OpenAI-compatible formats. When served through Ollama's OpenAI-compatible endpoint (`/v1/chat/completions`), tools are passed in the `tools` array parameter.

---

## Tool Definitions

### 1. Read File

Reads the contents of a file from the filesystem.

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file at the specified path. Returns the file contents as a string. Use this to examine existing code before making changes.",
    "parameters": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The absolute or relative path to the file to read (e.g., 'src/main.py' or '/home/user/project/config.json')"
        },
        "offset": {
          "type": "integer",
          "description": "Optional line number to start reading from (1-indexed). If not specified, reads from the beginning."
        },
        "limit": {
          "type": "integer",
          "description": "Optional maximum number of lines to read. If not specified, reads the entire file."
        }
      },
      "required": ["file_path"]
    }
  }
}
```

### 2. Write File

Creates a new file or completely overwrites an existing file.

```json
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
          "description": "The absolute or relative path to the file to write (e.g., 'src/newfile.py')"
        },
        "content": {
          "type": "string",
          "description": "The complete content to write to the file"
        }
      },
      "required": ["file_path", "content"]
    }
  }
}
```

### 3. Edit File (String Replacement)

Performs precise string replacement edits on existing files.

```json
{
  "type": "function",
  "function": {
    "name": "edit_file",
    "description": "Edit a file by replacing a specific string with new content. The old_string must match exactly (including whitespace and indentation). Use read_file first to see the exact content to replace. For multiple changes, call this function multiple times.",
    "parameters": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The path to the file to edit"
        },
        "old_string": {
          "type": "string",
          "description": "The exact string to find and replace. Must be unique within the file. Include enough surrounding context to make it unique."
        },
        "new_string": {
          "type": "string",
          "description": "The string to replace old_string with. Can be empty to delete the old_string."
        },
        "replace_all": {
          "type": "boolean",
          "description": "If true, replace all occurrences of old_string. If false (default), only replace the first occurrence and fail if not unique."
        }
      },
      "required": ["file_path", "old_string", "new_string"]
    }
  }
}
```

### 4. List Directory

Lists files and directories at a specified path.

```json
{
  "type": "function",
  "function": {
    "name": "list_directory",
    "description": "List the contents of a directory. Returns file and directory names. Use this to explore the project structure.",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "The directory path to list. Use '.' for current directory."
        },
        "recursive": {
          "type": "boolean",
          "description": "If true, list contents recursively. Default is false."
        },
        "pattern": {
          "type": "string",
          "description": "Optional glob pattern to filter results (e.g., '*.py', '**/*.tsx')"
        }
      },
      "required": ["path"]
    }
  }
}
```

### 5. Search Files (Glob)

Find files by name pattern.

```json
{
  "type": "function",
  "function": {
    "name": "glob_files",
    "description": "Find files matching a glob pattern. Returns a list of matching file paths. Use this to locate files by name or extension.",
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
}
```

### 6. Search Content (Grep)

Search for text patterns within files.

```json
{
  "type": "function",
  "function": {
    "name": "grep_search",
    "description": "Search for a text pattern within files. Returns matching lines with file paths and line numbers. Use this to find where specific code, functions, or variables are defined or used.",
    "parameters": {
      "type": "object",
      "properties": {
        "pattern": {
          "type": "string",
          "description": "Regular expression pattern to search for (e.g., 'function.*handleSubmit', 'class\\s+User')"
        },
        "path": {
          "type": "string",
          "description": "File or directory to search in. Defaults to current directory."
        },
        "file_pattern": {
          "type": "string",
          "description": "Optional glob pattern to filter which files to search (e.g., '*.py', '*.{ts,tsx}')"
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
}
```

### 7. Run Shell Command

Execute a shell command.

```json
{
  "type": "function",
  "function": {
    "name": "run_command",
    "description": "Execute a shell command and return its output. Use for running tests, builds, git commands, and other CLI operations. Commands run in the current working directory.",
    "parameters": {
      "type": "object",
      "properties": {
        "command": {
          "type": "string",
          "description": "The shell command to execute (e.g., 'npm test', 'git status', 'python -m pytest')"
        },
        "working_directory": {
          "type": "string",
          "description": "Optional directory to run the command in. Defaults to current directory."
        },
        "timeout": {
          "type": "integer",
          "description": "Optional timeout in seconds. Default is 120 seconds."
        }
      },
      "required": ["command"]
    }
  }
}
```

---

## Complete Tools Array

Here's the complete array to pass to the API:

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read the contents of a file at the specified path. Returns the file contents as a string. Use this to examine existing code before making changes.",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string",
              "description": "The absolute or relative path to the file to read"
            },
            "offset": {
              "type": "integer",
              "description": "Optional line number to start reading from (1-indexed)"
            },
            "limit": {
              "type": "integer",
              "description": "Optional maximum number of lines to read"
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
        "description": "Write content to a file at the specified path. Creates or overwrites the file.",
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
        "description": "Edit a file by replacing a specific string with new content. The old_string must match exactly.",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string",
              "description": "The path to the file to edit"
            },
            "old_string": {
              "type": "string",
              "description": "The exact string to find and replace"
            },
            "new_string": {
              "type": "string",
              "description": "The replacement string"
            },
            "replace_all": {
              "type": "boolean",
              "description": "If true, replace all occurrences"
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
        "description": "List the contents of a directory.",
        "parameters": {
          "type": "object",
          "properties": {
            "path": {
              "type": "string",
              "description": "The directory path to list"
            },
            "recursive": {
              "type": "boolean",
              "description": "If true, list contents recursively"
            },
            "pattern": {
              "type": "string",
              "description": "Optional glob pattern to filter results"
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
        "description": "Find files matching a glob pattern.",
        "parameters": {
          "type": "object",
          "properties": {
            "pattern": {
              "type": "string",
              "description": "Glob pattern to match files (e.g., '**/*.py')"
            },
            "path": {
              "type": "string",
              "description": "Optional base directory to search from"
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
        "description": "Search for a text pattern within files using regex.",
        "parameters": {
          "type": "object",
          "properties": {
            "pattern": {
              "type": "string",
              "description": "Regular expression pattern to search for"
            },
            "path": {
              "type": "string",
              "description": "File or directory to search in"
            },
            "file_pattern": {
              "type": "string",
              "description": "Glob pattern to filter which files to search"
            },
            "case_insensitive": {
              "type": "boolean",
              "description": "If true, case-insensitive matching"
            },
            "context_lines": {
              "type": "integer",
              "description": "Lines of context around matches"
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
        "description": "Execute a shell command and return its output.",
        "parameters": {
          "type": "object",
          "properties": {
            "command": {
              "type": "string",
              "description": "The shell command to execute"
            },
            "working_directory": {
              "type": "string",
              "description": "Directory to run the command in"
            },
            "timeout": {
              "type": "integer",
              "description": "Timeout in seconds (default 120)"
            }
          },
          "required": ["command"]
        }
      }
    }
  ]
}
```

---

## Usage with Ollama

### Starting the Model

```bash
ollama run devstral-small-2:24b
```

### API Call Example (Python)

```python
import requests
import json

response = requests.post(
    "http://localhost:11434/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    json={
        "model": "devstral-small-2:24b",
        "messages": [
            {
                "role": "system",
                "content": "You are a coding assistant. Use the provided tools to read, write, and edit files. Always read a file before editing it."
            },
            {
                "role": "user",
                "content": "Read the contents of src/main.py"
            }
        ],
        "tools": [
            # ... tools array from above
        ],
        "tool_choice": "auto"
    }
)

result = response.json()
print(json.dumps(result, indent=2))
```

### Using with Claude Code + Ollama

Per the Ollama documentation, configure Claude Code to use Ollama:

```bash
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_BASE_URL=http://localhost:11434
claude --model devstral-small-2:24b
```

**Note:** Claude Code has its own internal tool definitions. When using devstral through Claude Code's Ollama integration, the tool schemas are handled internally. This document is primarily useful for:
1. Building custom integrations
2. Understanding the expected tool format
3. Creating proxy servers that translate between formats

---

## Tool Call Response Format

When devstral decides to use a tool, it returns:

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "read_file",
              "arguments": "{\"file_path\": \"src/main.py\"}"
            }
          }
        ]
      }
    }
  ]
}
```

### Providing Tool Results

After executing the tool, return results with the `tool` role:

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "# Contents of src/main.py\ndef main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()"
}
```

---

## Best Practices for Devstral

1. **System Prompt**: Include clear instructions about tool usage:
   ```
   You are a coding assistant with access to file system tools.
   - Always use read_file before edit_file to see current content
   - Use glob_files or grep_search to find files before reading them
   - Make minimal, targeted edits rather than rewriting entire files
   - Run tests after making changes
   ```

2. **Context Window**: Devstral-small-2:24b supports large contexts, but keep tool responses concise when possible.

3. **Tool Choice**: Use `"tool_choice": "auto"` to let the model decide when to use tools.

4. **Error Handling**: Return clear error messages in tool results so the model can self-correct.

---

## References

- [Ollama Tool Support Blog](https://ollama.com/blog/tool-support)
- [Ollama OpenAI Compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Mistral Function Calling Docs](https://docs.mistral.ai/capabilities/function_calling)
- [Claude Code + Ollama Integration](https://docs.ollama.com/integrations/claude-code)
- [Devstral Model Info](https://mistral.ai/news/devstral-2507)
