# Ollama Tools Proxy

A proxy server that adds tool execution capabilities to Ollama models, enabling them to read, write, and edit files, search codebases, and run commands.

## Overview

This proxy sits between your client (Claude Code, custom scripts, etc.) and Ollama, automatically:

1. **Injecting tool definitions** into requests
2. **Executing tool calls** when the model requests them
3. **Returning results** to continue the conversation

This enables models like `devstral-small-2:24b` to effectively work with codebases.

## Installation

```bash
# Clone the repo
git clone https://github.com/yourusername/ollama-tools.git
cd ollama-tools

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .
```

For detailed tool schema documentation, see [docs/TOOL_SCHEMAS.md](docs/TOOL_SCHEMAS.md).

## Quick Start

### 1. Start Ollama with your model

```bash
ollama run devstral-small-2:24b
```

### 2. Start the proxy

```bash
# Basic usage - serves on localhost:8080
ollama-tools-proxy

# Specify working directory for file operations
ollama-tools-proxy --working-dir /path/to/your/project

# Restrict commands to safe ones
ollama-tools-proxy --command-allowlist "npm,git,python,pytest,ls,cat"
```

### 3. Connect Claude Code

```bash
ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_BASE_URL=http://localhost:8080 \
claude --model devstral-small-2:24b
```

Or use with any OpenAI-compatible client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="ollama"  # Required but not used
)

response = client.chat.completions.create(
    model="devstral-small-2:24b",
    messages=[
        {"role": "user", "content": "Read the package.json file and tell me what dependencies it has"}
    ]
)
print(response.choices[0].message.content)
```

## Available Tools

The proxy provides these tools to the model:

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with optional line offset/limit |
| `write_file` | Create or overwrite files |
| `edit_file` | Precise string replacement editing |
| `list_directory` | List directory contents |
| `glob_files` | Find files by pattern (e.g., `**/*.py`) |
| `grep_search` | Search file contents with regex |
| `run_command` | Execute shell commands |

## CLI Options

```
ollama-tools-proxy [OPTIONS]

Options:
  -p, --port PORT           Port to run on (default: 8080)
  -H, --host HOST           Host to bind to (default: 0.0.0.0)
  --ollama-url URL          Ollama server URL (default: http://localhost:11434)
  -w, --working-dir DIR     Working directory for file operations
  --allowed-dirs DIR [...]  Additional accessible directories
  --no-commands             Disable the run_command tool
  --command-allowlist LIST  Comma-separated allowed command prefixes
  --no-inject-tools         Don't auto-inject tool definitions
  --max-iterations N        Max tool iterations per request (default: 10)
  --default-model MODEL     Default model (default: devstral-small-2:24b)
  --log-level LEVEL         DEBUG, INFO, WARNING, ERROR (default: INFO)
  --reload                  Enable auto-reload for development
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OLLAMA_BASE_URL` | Ollama server URL |
| `OLLAMA_TOOLS_PORT` | Proxy server port |
| `OLLAMA_TOOLS_HOST` | Proxy server host |

## Security Considerations

### File Access

By default, the proxy only allows access to files within the working directory. Use `--allowed-dirs` to add additional directories:

```bash
ollama-tools-proxy --working-dir /project --allowed-dirs /shared/libs /config
```

### Command Execution

Command execution is enabled by default. To restrict it:

```bash
# Disable entirely
ollama-tools-proxy --no-commands

# Allow only specific command prefixes
ollama-tools-proxy --command-allowlist "npm test,npm run,git status,git diff,python -m pytest"
```

## API Endpoints

### OpenAI-Compatible

```
POST /v1/chat/completions
GET  /v1/models
```

### Anthropic-Compatible

```
POST /v1/messages
```

### Health Check

```
GET /health
```

## How Tool Execution Works

1. Client sends a chat completion request
2. Proxy injects tool definitions and forwards to Ollama
3. If the model returns tool calls:
   - Proxy executes each tool locally
   - Adds tool results to the conversation
   - Sends updated conversation back to Ollama
4. Repeat until model returns a text response (max 10 iterations)
5. Return final response to client

## Example Session

```
User: What files are in the src directory?

[Model calls list_directory(path="src")]
[Proxy executes and returns file list]

Model: The src directory contains:
- main.py
- utils.py
- config.py

User: Read the main.py file

[Model calls read_file(file_path="src/main.py")]
[Proxy executes and returns file contents]

Model: Here's the contents of main.py:
[Shows file contents with analysis]
```

## Programmatic Usage

You can also use the components directly in Python:

```python
from ollama_tools import ToolExecutor, get_tools_array

# Create executor
executor = ToolExecutor(
    working_directory="/path/to/project",
    allow_commands=True
)

# Execute a tool
result = executor.execute("read_file", {"file_path": "README.md"})
print(result)

# Get tool schemas for API calls
tools = get_tools_array()
```

## Using with the Proxy Programmatically

```python
import asyncio
from ollama_tools.proxy import OllamaToolProxy, ProxyConfig

async def main():
    config = ProxyConfig(
        ollama_base_url="http://localhost:11434",
        working_directory="/path/to/project"
    )

    proxy = OllamaToolProxy(config)

    result = await proxy.chat_completion(
        messages=[
            {"role": "user", "content": "List all Python files in this project"}
        ],
        model="devstral-small-2:24b"
    )

    print(result["choices"][0]["message"]["content"])
    await proxy.close()

asyncio.run(main())
```

## Troubleshooting

### "Connection refused" to Ollama

Make sure Ollama is running:
```bash
ollama serve
```

### Model not found

Pull the model first:
```bash
ollama pull devstral-small-2:24b
```

### Permission denied errors

Check that the working directory and any paths the model tries to access are within allowed directories.

### Command execution disabled

If you see "Command execution is disabled", either:
- Remove the `--no-commands` flag
- Add the command to `--command-allowlist`

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/ --fix
```

## License

MIT
