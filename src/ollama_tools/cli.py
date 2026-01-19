"""Command-line interface for the Ollama Tools Proxy."""

import argparse
import logging
import os
import sys

import uvicorn

from .proxy import ProxyConfig, create_app


def main():
    """Run the Ollama Tools Proxy server."""
    parser = argparse.ArgumentParser(
        description="Ollama Tools Proxy - Adds tool execution to Ollama models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start with defaults (localhost:8080, tools enabled)
  ollama-tools-proxy

  # Specify port and working directory
  ollama-tools-proxy --port 8000 --working-dir /path/to/project

  # Restrict to specific commands
  ollama-tools-proxy --command-allowlist "npm,git,python,pytest"

  # Connect to remote Ollama
  ollama-tools-proxy --ollama-url http://192.168.1.100:11434

Environment variables:
  OLLAMA_BASE_URL     - Ollama server URL (default: http://localhost:11434)
  OLLAMA_TOOLS_PORT   - Proxy server port (default: 8080)
  OLLAMA_TOOLS_HOST   - Proxy server host (default: 0.0.0.0)
        """
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.environ.get("OLLAMA_TOOLS_PORT", "8080")),
        help="Port to run the proxy server on (default: 8080)"
    )
    parser.add_argument(
        "--host", "-H",
        default=os.environ.get("OLLAMA_TOOLS_HOST", "0.0.0.0"),
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="Ollama server URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--working-dir", "-w",
        default=os.getcwd(),
        help="Working directory for file operations (default: current directory)"
    )
    parser.add_argument(
        "--allowed-dirs",
        nargs="*",
        help="Additional directories that can be accessed (default: working directory only)"
    )
    parser.add_argument(
        "--no-commands",
        action="store_true",
        help="Disable the run_command tool"
    )
    parser.add_argument(
        "--command-allowlist",
        help="Comma-separated list of allowed command prefixes (e.g., 'npm,git,python')"
    )
    parser.add_argument(
        "--no-inject-tools",
        action="store_true",
        help="Don't automatically inject tool definitions"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum tool execution iterations per request (default: 10)"
    )
    parser.add_argument(
        "--default-model",
        default="devstral-small-2:24b",
        help="Default model to use if not specified in request"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Build config
    allowed_dirs = list(args.allowed_dirs) if args.allowed_dirs else None
    if allowed_dirs is None:
        allowed_dirs = [args.working_dir]
    elif args.working_dir not in allowed_dirs:
        allowed_dirs.append(args.working_dir)

    command_allowlist = None
    if args.command_allowlist:
        command_allowlist = [c.strip() for c in args.command_allowlist.split(",")]

    config = ProxyConfig(
        ollama_base_url=args.ollama_url,
        working_directory=args.working_dir,
        allowed_directories=allowed_dirs,
        allow_commands=not args.no_commands,
        command_allowlist=command_allowlist,
        inject_tools=not args.no_inject_tools,
        max_tool_iterations=args.max_iterations,
        default_model=args.default_model,
    )

    # Print startup info
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                   Ollama Tools Proxy                        ║
╠══════════════════════════════════════════════════════════════╣
║  Proxy URL:      http://{args.host}:{args.port}
║  Ollama URL:     {config.ollama_base_url}
║  Working Dir:    {config.working_directory}
║  Commands:       {"Enabled" if config.allow_commands else "Disabled"}
║  Default Model:  {config.default_model}
╚══════════════════════════════════════════════════════════════╝

Use with Claude Code:
  ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:{args.port} claude --model {config.default_model}

Use with OpenAI-compatible clients:
  POST http://localhost:{args.port}/v1/chat/completions
""")

    # Create app with config
    app = create_app(config)

    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower()
    )


if __name__ == "__main__":
    main()
