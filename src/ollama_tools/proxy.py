"""
Proxy server that routes requests to Ollama and handles tool execution.

This server sits between clients and Ollama, automatically:
1. Injecting tool definitions into requests
2. Executing tool calls when the model requests them
3. Returning tool results to continue the conversation
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .executor import ToolExecutor
from .schemas import TOOLS

logger = logging.getLogger(__name__)


class ProxyConfig(BaseModel):
    """Configuration for the proxy server."""

    ollama_base_url: str = "http://localhost:11434"
    ollama_auth_token: str | None = None  # Bearer token for authenticated Ollama endpoints
    use_anthropic_api: bool = False  # Use /v1/messages instead of /v1/chat/completions
    working_directory: str | None = None
    allowed_directories: list[str] | None = None
    allow_commands: bool = True
    command_allowlist: list[str] | None = None
    inject_tools: bool = True
    max_tool_iterations: int = 10
    default_model: str = "devstral-small-2:24b"
    force_model: bool = False  # Always use default_model, ignore client-specified models


class OllamaToolProxy:
    """Proxy that handles tool execution between client and Ollama."""

    def __init__(self, config: ProxyConfig | None = None):
        self.config = config or ProxyConfig()
        self.executor = ToolExecutor(
            working_directory=self.config.working_directory,
            allowed_directories=self.config.allowed_directories,
            allow_commands=self.config.allow_commands,
            command_allowlist=self.config.command_allowlist,
        )

        # Build headers for Ollama requests (auth if configured)
        self.ollama_headers: dict[str, str] = {}
        if self.config.ollama_auth_token:
            self.ollama_headers["Authorization"] = f"Bearer {self.config.ollama_auth_token}"

        self.client = httpx.AsyncClient(timeout=300.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = "auto",
        stream: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """
        Handle a chat completion request with automatic tool execution.

        Args:
            messages: Conversation messages
            model: Model to use (defaults to config.default_model)
            tools: Tool definitions (defaults to built-in tools if inject_tools is True)
            tool_choice: How to handle tool selection
            stream: Whether to stream the response
            **kwargs: Additional parameters to pass to Ollama

        Returns:
            OpenAI-compatible chat completion response
        """
        model = model or self.config.default_model

        # Inject tools if enabled and not provided
        if self.config.inject_tools and tools is None:
            tools = TOOLS

        # Build request for Ollama
        request_body = {
            "model": model,
            "messages": messages,
            "stream": False,  # We handle streaming separately
            **kwargs
        }

        if tools:
            request_body["tools"] = tools
        if tool_choice:
            request_body["tool_choice"] = tool_choice

        # Execute with tool loop
        current_messages = list(messages)
        iterations = 0

        while iterations < self.config.max_tool_iterations:
            iterations += 1

            # Call Ollama
            response = await self._call_ollama(request_body, current_messages)

            # Check for tool calls
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, return final response
                return response

            # Execute tool calls
            logger.info(f"Executing {len(tool_calls)} tool call(s)")

            # Add assistant message with tool calls
            current_messages.append(message)

            # Execute each tool and add results
            for tool_call in tool_calls:
                tool_result = self.executor.execute_tool_call(tool_call)
                current_messages.append(tool_result)

                func_name = tool_call.get("function", {}).get("name", "unknown")
                logger.info(f"Executed tool: {func_name}")

            # Update request with new messages
            request_body["messages"] = current_messages

        # Max iterations reached
        logger.warning(f"Max tool iterations ({self.config.max_tool_iterations}) reached")
        return response

    async def _call_ollama(
        self,
        request_body: dict[str, Any],
        messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Make a request to Ollama using OpenAI-compatible API."""
        request_body["messages"] = messages

        url = f"{self.config.ollama_base_url}/v1/chat/completions"

        try:
            response = await self.client.post(
                url,
                json=request_body,
                headers=self.ollama_headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama request failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama request error: {e}")
            raise

    async def _call_ollama_anthropic(
        self,
        request_body: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a request to Ollama using Anthropic-compatible API (/v1/messages) - non-streaming."""
        url = f"{self.config.ollama_base_url}/v1/messages"

        # Force non-streaming for this method
        request_body = {**request_body, "stream": False}

        # Override model if force_model is enabled
        if self.config.force_model:
            client_model = request_body.get("model", "")
            if client_model != self.config.default_model:
                logger.info(f"Forcing model: {client_model} -> {self.config.default_model}")
                request_body["model"] = self.config.default_model

        logger.debug(f"Anthropic API request to {url}: {request_body}")

        try:
            response = await self.client.post(
                url,
                json=request_body,
                headers=self.ollama_headers
            )
            response.raise_for_status()

            # Log raw response for debugging
            raw_text = response.text
            logger.debug(f"Anthropic API raw response: {raw_text[:500] if raw_text else '(empty)'}")

            if not raw_text:
                logger.error("Ollama returned empty response body")
                raise ValueError("Empty response from Ollama")

            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama Anthropic API request failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Ollama Anthropic API request error: {e}")
            raise

    async def _stream_ollama_anthropic(
        self,
        request_body: dict[str, Any]
    ) -> AsyncIterator[bytes]:
        """Stream a request to Ollama using Anthropic-compatible API (/v1/messages)."""
        url = f"{self.config.ollama_base_url}/v1/messages"

        # Ensure streaming is enabled
        request_body = {**request_body, "stream": True}

        # Override model if force_model is enabled
        if self.config.force_model:
            client_model = request_body.get("model", "")
            if client_model != self.config.default_model:
                logger.info(f"Forcing model: {client_model} -> {self.config.default_model}")
                request_body["model"] = self.config.default_model

        logger.debug(f"Anthropic API streaming request to {url}")

        async with self.client.stream(
            "POST",
            url,
            json=request_body,
            headers=self.ollama_headers
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion response.

        Note: Tool calls are executed before streaming begins.
        The final response after tool execution is streamed.
        """
        # First, execute with tools (non-streaming)
        result = await self.chat_completion(
            messages=messages,
            model=model,
            tools=tools,
            stream=False,
            **kwargs
        )

        # Stream the final response
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Yield as SSE events
        for i in range(0, len(content), 50):
            chunk = content[i:i+50]
            data = {
                "choices": [{
                    "delta": {"content": chunk},
                    "index": 0
                }]
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.01)

        yield "data: [DONE]\n\n"


def create_app(config: ProxyConfig | None = None) -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Ollama Tools Proxy",
        description="Proxy server that adds tool execution capabilities to Ollama models",
        version="0.1.0"
    )

    proxy = OllamaToolProxy(config)

    @app.on_event("shutdown")
    async def shutdown():
        await proxy.close()

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    # Stub endpoints to silence Claude Code 404s
    @app.post("/api/event_logging/batch")
    async def event_logging_batch():
        """Stub for Claude Code telemetry - silently accept and ignore."""
        return {"status": "ok"}

    @app.post("/v1/messages/count_tokens")
    async def count_tokens(request: Request):
        """Stub for token counting - return estimate based on message length."""
        try:
            body = await request.json()
            # Rough estimate: ~4 chars per token
            text = str(body.get("messages", []))
            estimated_tokens = len(text) // 4
            return {"input_tokens": estimated_tokens}
        except Exception:
            return {"input_tokens": 0}

    @app.get("/v1/models")
    async def list_models():
        """Proxy model list from Ollama."""
        try:
            response = await proxy.client.get(
                f"{proxy.config.ollama_base_url}/v1/models",
                headers=proxy.ollama_headers
            )
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        """Handle chat completion requests with tool execution."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        messages = body.get("messages", [])
        model = body.get("model")
        tools = body.get("tools")
        tool_choice = body.get("tool_choice", "auto")
        stream = body.get("stream", False)

        # Remove fields we handle specially
        kwargs = {k: v for k, v in body.items()
                  if k not in ["messages", "model", "tools", "tool_choice", "stream"]}

        try:
            if stream:
                return StreamingResponse(
                    proxy.chat_completion_stream(
                        messages=messages,
                        model=model,
                        tools=tools,
                        **kwargs
                    ),
                    media_type="text/event-stream"
                )
            else:
                result = await proxy.chat_completion(
                    messages=messages,
                    model=model,
                    tools=tools,
                    tool_choice=tool_choice,
                    stream=False,
                    **kwargs
                )
                return result
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            logger.exception("Error processing request")
            raise HTTPException(status_code=500, detail=str(e))

    # Also support Anthropic-style endpoint for Claude Code compatibility
    @app.post("/v1/messages")
    async def messages_endpoint(request: Request):
        """
        Anthropic-style messages endpoint.
        If use_anthropic_api is enabled, forwards directly to Ollama's /v1/messages.
        Otherwise, converts to OpenAI format, processes, and converts back.
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        # Use default model if not specified
        if "model" not in body or not body["model"]:
            body["model"] = proxy.config.default_model

        # Check if streaming is requested
        stream = body.get("stream", False)

        # If using Anthropic API directly, forward the request
        if proxy.config.use_anthropic_api:
            try:
                if stream:
                    # Stream the response back to client
                    return StreamingResponse(
                        proxy._stream_ollama_anthropic(body),
                        media_type="text/event-stream"
                    )
                else:
                    result = await proxy._call_ollama_anthropic(body)
                    return result
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
            except Exception as e:
                logger.exception("Error forwarding Anthropic request")
                raise HTTPException(status_code=500, detail=str(e))

        # Otherwise, convert to OpenAI format and process
        messages = []
        system_prompt = body.get("system", "")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in body.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Handle content blocks
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)

            messages.append({"role": role, "content": content})

        model = body.get("model", proxy.config.default_model)

        try:
            result = await proxy.chat_completion(
                messages=messages,
                model=model,
                stream=False
            )

            # Convert back to Anthropic format
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")

            return {
                "id": result.get("id", "msg_001"),
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": content}],
                "model": model,
                "stop_reason": "end_turn",
                "usage": result.get("usage", {})
            }
        except Exception as e:
            logger.exception("Error processing Anthropic-style request")
            raise HTTPException(status_code=500, detail=str(e))

    return app


# Default app instance for uvicorn
app = create_app()
