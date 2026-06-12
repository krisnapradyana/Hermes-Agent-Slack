"""
BytePlus Ark — Seedance MCP Server
Exposes BytePlus Ark video generation as MCP tools via StreamableHTTP transport.
Hermes connects to: http://seedance-mcp:8765/mcp
"""

import os
import time
import json
import logging
import requests
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Monkeypatch streamable_http to gracefully handle ClosedResourceError ──────
try:
    import anyio
    from starlette.types import Scope, Receive, Send
    from starlette.requests import Request
    from mcp.types import JSONRPCMessage, JSONRPCRequest, JSONRPCResponse, JSONRPCError
    from mcp.server.streamable_http import (
        ServerMessageMetadata,
        SessionMessage,
        EventMessage,
        StreamableHTTPServerTransport,
        CONTENT_TYPE_SSE,
        MCP_SESSION_ID_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
        DEFAULT_NEGOTIATED_VERSION,
        HTTPStatus,
        PARSE_ERROR,
        INVALID_PARAMS,
        INTERNAL_ERROR,
    )
    from sse_starlette import EventSourceResponse
    from pydantic import ValidationError

    async def patched_handle_post_request(self, scope: Scope, request: Request, receive: Receive, send: Send) -> None:
        """Handle POST requests containing JSON-RPC messages, monkeypatched to gracefully handle ClosedResourceError."""
        writer = self._read_stream_writer
        if writer is None:  # pragma: no cover
            raise ValueError("No read stream writer available. Ensure connect() is called first.")
        try:
            # Validate Accept header
            if not await self._validate_accept_header(request, scope, send):
                return

            # Validate Content-Type
            if not self._check_content_type(request):  # pragma: no cover
                response = self._create_error_response(
                    "Unsupported Media Type: Content-Type must be application/json",
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                )
                await response(scope, receive, send)
                return

            # Parse the body - only read it once
            body = await request.body()

            try:
                raw_message = json.loads(body)
            except json.JSONDecodeError as e:
                response = self._create_error_response(f"Parse error: {str(e)}", HTTPStatus.BAD_REQUEST, PARSE_ERROR)
                await response(scope, receive, send)
                return

            try:  # pragma: no cover
                message = JSONRPCMessage.model_validate(raw_message)
            except ValidationError as e:  # pragma: no cover
                response = self._create_error_response(
                    f"Validation error: {str(e)}",
                    HTTPStatus.BAD_REQUEST,
                    INVALID_PARAMS,
                )
                await response(scope, receive, send)
                return

            # Check if this is an initialization request
            is_initialization_request = (
                isinstance(message.root, JSONRPCRequest) and message.root.method == "initialize"
            )  # pragma: no cover

            if is_initialization_request:  # pragma: no cover
                # Check if the server already has an established session
                if self.mcp_session_id:
                    # Check if request has a session ID
                    request_session_id = self._get_session_id(request)

                    # If request has a session ID but doesn't match, return 404
                    if request_session_id and request_session_id != self.mcp_session_id:
                        response = self._create_error_response(
                            "Not Found: Invalid or expired session ID",
                            HTTPStatus.NOT_FOUND,
                        )
                        await response(scope, receive, send)
                        return
            elif not await self._validate_request_headers(request, send):  # pragma: no cover
                return

            # For notifications and responses only, return 202 Accepted
            if not isinstance(message.root, JSONRPCRequest):  # pragma: no cover
                # Create response object and send it
                response = self._create_json_response(
                    None,
                    HTTPStatus.ACCEPTED,
                )
                await response(scope, receive, send)

                # Process the message after sending the response
                metadata = ServerMessageMetadata(request_context=request)
                session_message = SessionMessage(message, metadata=metadata)
                try:
                    await writer.send(session_message)
                except anyio.ClosedResourceError:
                    logger.debug("Client disconnected during notification/response send (ClosedResourceError)")
                return

            # Extract protocol version for priming event decision.
            # For initialize requests, get from request params.
            # For other requests, get from header (already validated).
            protocol_version = (
                str(message.root.params.get("protocolVersion", DEFAULT_NEGOTIATED_VERSION))
                if is_initialization_request and message.root.params
                else request.headers.get(MCP_PROTOCOL_VERSION_HEADER, DEFAULT_NEGOTIATED_VERSION)
            )

            # Extract the request ID outside the try block for proper scope
            request_id = str(message.root.id)  # pragma: no cover
            # Register this stream for the request ID
            self._request_streams[request_id] = anyio.create_memory_object_stream[EventMessage](0)  # pragma: no cover
            request_stream_reader = self._request_streams[request_id][1]  # pragma: no cover

            if self.is_json_response_enabled:  # pragma: no cover
                # Process the message
                metadata = ServerMessageMetadata(request_context=request)
                session_message = SessionMessage(message, metadata=metadata)
                try:
                    await writer.send(session_message)
                except anyio.ClosedResourceError:
                    logger.debug("Client disconnected during json request send (ClosedResourceError)")
                    await self._clean_up_memory_streams(request_id)
                    return

                try:
                    # Process messages from the request-specific stream
                    # We need to collect all messages until we get a response
                    response_message = None

                    # Use similar approach to SSE writer for consistency
                    async for event_message in request_stream_reader:
                        # If it's a response, this is what we're waiting for
                        if isinstance(event_message.message.root, JSONRPCResponse | JSONRPCError):
                            response_message = event_message.message
                            break
                        # For notifications and request, keep waiting
                        else:
                            logger.debug(f"received: {event_message.message.root.method}")

                    # At this point we should have a response
                    if response_message:
                        # Create JSON response
                        response = self._create_json_response(response_message)
                        await response(scope, receive, send)
                    else:
                        # This shouldn't happen in normal operation
                        logger.error("No response message received before stream closed")
                        response = self._create_error_response(
                            "Error processing request: No response received",
                            HTTPStatus.INTERNAL_SERVER_ERROR,
                        )
                        await response(scope, receive, send)
                except Exception:
                    logger.exception("Error processing JSON response")
                    response = self._create_error_response(
                        "Error processing request",
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        INTERNAL_ERROR,
                    )
                    await response(scope, receive, send)
                finally:
                    await self._clean_up_memory_streams(request_id)
            else:  # pragma: no cover
                # Create SSE stream
                sse_stream_writer, sse_stream_reader = anyio.create_memory_object_stream[dict[str, str]](0)

                # Store writer reference so close_sse_stream() can close it
                self._sse_stream_writers[request_id] = sse_stream_writer

                async def sse_writer():
                    # Get the request ID from the incoming request message
                    try:
                        async with sse_stream_writer, request_stream_reader:
                            # Send priming event for SSE resumability
                            await self._maybe_send_priming_event(request_id, sse_stream_writer, protocol_version)

                            # Process messages from the request-specific stream
                            async for event_message in request_stream_reader:
                                # Build the event data
                                event_data = self._create_event_data(event_message)
                                await sse_stream_writer.send(event_data)

                                # If response, remove from pending streams and close
                                if isinstance(
                                    event_message.message.root,
                                    JSONRPCResponse | JSONRPCError,
                                ):
                                    break
                    except anyio.ClosedResourceError:
                        # Expected when close_sse_stream() is called
                        logger.debug("SSE stream closed by close_sse_stream()")
                    except Exception:
                        logger.exception("Error in SSE writer")
                    finally:
                        logger.debug("Closing SSE writer")
                        self._sse_stream_writers.pop(request_id, None)
                        await self._clean_up_memory_streams(request_id)

                # Create and start EventSourceResponse
                # SSE stream mode (original behavior)
                # Set up headers
                headers = {
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "Content-Type": CONTENT_TYPE_SSE,
                    **({MCP_SESSION_ID_HEADER: self.mcp_session_id} if self.mcp_session_id else {}),
                }
                response = EventSourceResponse(
                    content=sse_stream_reader,
                    data_sender_callable=sse_writer,
                    headers=headers,
                )

                # Start the SSE response (this will send headers immediately)
                try:
                    # First send the response to establish the SSE connection
                    async with anyio.create_task_group() as tg:
                        tg.start_soon(response, scope, receive, send)
                        try:
                            # Then send the message to be processed by the server
                            session_message = self._create_session_message(message, request, request_id, protocol_version)
                            await writer.send(session_message)
                        except anyio.ClosedResourceError:
                            logger.info("Gracefully handled client disconnection (ClosedResourceError) during message send")
                            tg.cancel_scope.cancel()
                except Exception:
                    logger.exception("SSE response error")
                    await sse_stream_writer.aclose()
                    await sse_stream_reader.aclose()
                    await self._clean_up_memory_streams(request_id)

        except Exception as err:  # pragma: no cover
            logger.exception("Error handling POST request")
            response = self._create_error_response(
                f"Error handling POST request: {err}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                INTERNAL_ERROR,
            )
            await response(scope, receive, send)
            if writer:
                try:
                    await writer.send(Exception(err))
                except anyio.ClosedResourceError:
                    pass
            return

    StreamableHTTPServerTransport._handle_post_request = patched_handle_post_request
    logger.info("Successfully patched StreamableHTTPServerTransport._handle_post_request to gracefully handle ClosedResourceError")
except Exception as e:
    logger.error(f"Failed to patch StreamableHTTPServerTransport: {e}")

# ── Config ────────────────────────────────────────────────────────────────────
ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
PORT = int(os.environ.get("MCP_PORT", "8765"))

MODELS = {
    "seedance-2.0":          "dreamina-seedance-2-0-260128",
    "seedance-2.0-fast":     "dreamina-seedance-2-0-fast-260128",
    "seedance-1.5-pro":      "doubao-seedance-1-5-pro-250610",
    "seedance-1.0-pro":      "doubao-seedance-1-0-pro-250528",
    "seedance-1.0-pro-fast": "doubao-seedance-1-0-pro-fast-i2v-250528",
    "seedance-1.0-lite":     "doubao-seedance-1-0-lite-t2v-250428",
}
DEFAULT_MODEL = "seedance-2.0"

logger.info(f"Starting Seedance MCP Server on port {PORT}")
logger.info(f"ARK_API_KEY set: {'yes' if ARK_API_KEY else 'NO — set ARK_API_KEY env var'}")

# ── Helpers ────────────────────────────────────────────────────────────────────

def ark_headers():
    return {
        "Authorization": f"Bearer {ARK_API_KEY}",
        "Content-Type": "application/json",
    }

def create_task(payload: dict) -> dict:
    logger.info(f"Creating task: model={payload.get('model')}")
    resp = requests.post(
        f"{BASE_URL}/contents/generations/tasks",
        headers=ark_headers(),
        json=payload,
        timeout=30,
    )
    if resp.status_code != 200:
        logger.error(f"Failed to create task. Status: {resp.status_code}, Response: {resp.text}")
    resp.raise_for_status()
    return resp.json()

def get_task_status(task_id: str) -> dict:
    resp = requests.get(
        f"{BASE_URL}/contents/generations/tasks/{task_id}",
        headers=ark_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        logger.error(f"Failed to get task status. Status: {resp.status_code}, Response: {resp.text}")
    resp.raise_for_status()
    return resp.json()

async def poll_task(task_id: str, timeout: int = 900, interval: int = 10) -> dict:
    logger.info(f"Polling task {task_id}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = await anyio.to_thread.run_sync(get_task_status, task_id)
        status = data.get("status", "")
        logger.info(f"Task {task_id} status: {status}")
        if status == "succeeded":
            return data
        elif status in ("failed", "cancelled"):
            logger.error(f"Task {task_id} failed or cancelled. Full response: {json.dumps(data)}")
            raise RuntimeError(f"Task {task_id} ended with status: {status}. Detail: {json.dumps(data)}")
        await anyio.sleep(interval)
    raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

def resolve_model(name: str) -> str:
    return MODELS.get(name, MODELS[DEFAULT_MODEL])

# ── FastMCP Server ─────────────────────────────────────────────────────────────

mcp = FastMCP("seedance-byteplus", host="0.0.0.0", port=PORT)


@mcp.tool()
def seedance_list_models() -> str:
    """List all available BytePlus Seedance video generation models."""
    lines = ["Available BytePlus Seedance models:\n"]
    for alias, model_id in MODELS.items():
        lines.append(f"  • {alias}: {model_id}")
    return "\n".join(lines)


@mcp.tool()
def seedance_get_task(task_id: str) -> str:
    """
    Check the status of a Seedance video generation task.
    
    Args:
        task_id: The task ID returned from seedance_generate_video
    """
    data = get_task_status(task_id)
    return json.dumps(data, indent=2)


@mcp.tool()
async def seedance_generate_video(
    prompt: str,
    model: str = DEFAULT_MODEL,
    resolution: str = "720p",
    duration: int = 5,
    aspect_ratio: str = "16:9",
) -> str:
    """
    Generate an AI video from a text prompt using BytePlus Seedance.
    
    Args:
        prompt: Detailed description of the video to generate
        model: Model to use. Options: seedance-2.0 (best), seedance-2.0-fast, 
               seedance-1.5-pro, seedance-1.0-pro, seedance-1.0-pro-fast, seedance-1.0-lite
        resolution: Video resolution: 480p, 720p, or 1080p (default: 720p)
        duration: Video duration in seconds: 5 or 10 (default: 5)
        aspect_ratio: Aspect ratio: 16:9, 9:16, 1:1, 4:3, 3:4, 21:9 (default: 16:9)
    
    Returns:
        JSON with task_id, status, and video_url when complete
    """
    model_id = resolve_model(model)
    payload = {
        "model": model_id,
        "content": [{"type": "text", "text": prompt}],
        "ratio": aspect_ratio,
        "resolution": resolution,
        "duration": duration,
    }

    task = await anyio.to_thread.run_sync(create_task, payload)
    task_id = task.get("id") or task.get("task_id")
    
    result = await poll_task(task_id)
    video_url = (
        result.get("content", {}).get("video_url")
        or result.get("video_url")
        or result.get("output", {}).get("video_url")
    )

    return json.dumps({
        "task_id": task_id,
        "status": "succeeded",
        "video_url": video_url,
        "model": model_id,
        "resolution": resolution,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
    }, indent=2)


@mcp.tool()
async def seedance_generate_video_from_image(
    prompt: str,
    image_url: str,
    model: str = "seedance-1.0-pro",
    resolution: str = "720p",
    duration: int = 5,
    aspect_ratio: str = "16:9",
) -> str:
    """
    Animate an existing image into a video using BytePlus Seedance image-to-video.
    
    Args:
        prompt: Description of how to animate the image
        image_url: URL of the source image to animate
        model: Model to use (default: seedance-1.0-pro)
        resolution: Video resolution: 480p, 720p, or 1080p
        duration: Duration in seconds: 5 or 10
        aspect_ratio: Aspect ratio: 16:9, 9:16, 1:1, 4:3, etc.
    
    Returns:
        JSON with task_id, status, and video_url when complete
    """
    model_id = resolve_model(model)
    payload = {
        "model": model_id,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
        "ratio": aspect_ratio,
        "resolution": resolution,
        "duration": duration,
    }

    task = await anyio.to_thread.run_sync(create_task, payload)
    task_id = task.get("id") or task.get("task_id")
    
    result = await poll_task(task_id)
    video_url = (
        result.get("content", {}).get("video_url")
        or result.get("video_url")
    )

    return json.dumps({
        "task_id": task_id,
        "status": "succeeded",
        "video_url": video_url,
        "model": model_id,
    }, indent=2)


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
