"""Ollama Tools - Tool execution layer for LLM function calling."""

__version__ = "0.1.0"

from .executor import ToolExecutor
from .schemas import TOOLS, get_tools_array

__all__ = ["ToolExecutor", "TOOLS", "get_tools_array"]
