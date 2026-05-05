import asyncio
import json
import sys
import uuid
from asyncio.subprocess import PIPE
from config import now_ist
from pathlib import Path

from pounce import config


class MCPClient:
    """Minimal MCP stdio client — sends JSON-RPC requests, returns results."""

    def __init__(self, proc: asyncio.subprocess.Process):
        self._proc = proc
        self._pending: dict[str, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None

    async def connect(self) -> None:
        await self._initialize()
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _initialize(self) -> None:
        init_msg = {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pounce", "version": "0.1.0"},
            },
        }
        await self._send_raw(init_msg)
        # Read the init response directly (before the reader loop starts)
        line = await self._proc.stdout.readline()
        response = json.loads(line.decode())
        if "error" in response:
            raise RuntimeError(f"MCP init failed: {response['error']}")

        # Send initialized notification
        await self._send_raw({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def _read_loop(self) -> None:
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode())
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending[msg_id].set_result(msg)
            except json.JSONDecodeError:
                pass

    async def _send_raw(self, msg: dict) -> None:
        data = json.dumps(msg).encode() + b"\n"
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool and return its result."""
        call_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[call_id] = future

        await self._send_raw({
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        })

        try:
            response = await asyncio.wait_for(future, timeout=config.POUNCE_STEP_TIMEOUT / 1000)
        finally:
            self._pending.pop(call_id, None)

        if "error" in response:
            raise RuntimeError(f"MCP tool error ({tool_name}): {response['error']}")
        return response.get("result", {})

    async def list_tools(self) -> list[dict]:
        """Fetch available tools from the MCP server."""
        call_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[call_id] = future

        await self._send_raw({
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/list",
        })

        response = await asyncio.wait_for(future, timeout=10)
        return response.get("result", {}).get("tools", [])

    async def disconnect(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self._proc.stdin:
            self._proc.stdin.close()


class PounceSession:
    """
    Manages the Playwright MCP server subprocess and MCP client connection.
    Use as an async context manager.
    """

    def __init__(self, headless: bool | None = None):
        self.headless = headless if headless is not None else config.POUNCE_HEADLESS
        self._proc: asyncio.subprocess.Process | None = None
        self.client: MCPClient | None = None
        self._run_id: str = str(uuid.uuid4())[:8]
        self._screenshot_dir: Path = config.SCREENSHOTS_DIR / self._run_id
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> "PounceSession":
        npx = "npx.cmd" if sys.platform == "win32" else "npx"
        args = [npx, "--yes", "@playwright/mcp@0.0.68"]
        if self.headless:
            args.append("--headless")

        self._proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=PIPE,
            stdout=PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.client = MCPClient(self._proc)
        await self.client.connect()
        return self

    async def __aexit__(self, *args) -> None:
        if self.client:
            await self.client.disconnect()
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()

    async def screenshot(self, label: str = "screenshot") -> Path:
        """Take a screenshot and save it locally. Returns the file path."""
        ts = now_ist().strftime("%H%M%S")
        path = self._screenshot_dir / f"{ts}_{label}.png"
        result = await self.client.call_tool(
            "browser_take_screenshot", {"path": str(path)}
        )
        return path

    async def navigate(self, url: str) -> None:
        await self.client.call_tool("browser_navigate", {"url": url})
        await asyncio.sleep(2)

    async def get_page_snapshot(self) -> str:
        """Return the current page accessibility tree snapshot as text."""
        result = await self.client.call_tool("browser_snapshot", {})
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text":
                return item.get("text", "")
        return ""
