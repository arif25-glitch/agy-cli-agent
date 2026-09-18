import asyncio
import json
import logging
import shutil
from typing import AsyncGenerator, Optional, Union
from gemini_hermes.config import config
from gemini_hermes.brain.stream_parser import (
    TokenDelta,
    ThinkingDelta,
    ToolExecutionUpdate,
    ForwarderResult,
    parse_ndjson_line,
)

logger = logging.getLogger("gemini-hermes.agy_forwarder")


class AgyForwarder:
    def __init__(
        self,
        agy_bin: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        dangerously_skip_permissions: Optional[bool] = None,
    ):
        self.agy_bin = agy_bin or config.agy_bin or shutil.which("agy") or "agy"
        self.reasoning_effort = reasoning_effort or config.reasoning_effort
        self.dangerously_skip_permissions = (
            dangerously_skip_permissions
            if dangerously_skip_permissions is not None
            else config.dangerously_skip_permissions
        )

    def _build_command(self, prompt: str, conversation_id: Optional[str] = None) -> list:
        cmd = [
            self.agy_bin,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--effort",
            self.reasoning_effort,
        ]
        if self.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if conversation_id:
            cmd.extend(["--conversation", conversation_id])
        return cmd

    async def check_health(self) -> dict:
        try:
            cmd = [self.agy_bin, "-p", "ping", "--output-format", "json", "--effort", "low"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                return {
                    "ok": False,
                    "agy_bin": self.agy_bin,
                    "error": "Timeout waiting for agy CLI response (possible unauthenticated session or network issue).",
                }

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            if "Authentication required" in stdout_str or "Authentication required" in stderr_str:
                return {
                    "ok": False,
                    "auth_required": True,
                    "agy_bin": self.agy_bin,
                    "error": "Authentication required. No active login token session found.",
                }

            if proc.returncode == 0:
                try:
                    data = json.loads(stdout_str)
                    return {
                        "ok": True,
                        "agy_bin": self.agy_bin,
                        "status": data.get("status"),
                        "conversation_id": data.get("conversation_id"),
                        "sample_response": data.get("response", "").strip(),
                    }
                except Exception:
                    return {
                        "ok": True,
                        "agy_bin": self.agy_bin,
                        "raw_output": stdout_str,
                    }
            else:
                return {
                    "ok": False,
                    "agy_bin": self.agy_bin,
                    "error": stderr_str or stdout_str or f"Exit code {proc.returncode}",
                }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"ok": False, "agy_bin": self.agy_bin, "error": str(e)}

    async def forward_stream(
        self, prompt: str, conversation_id: Optional[str] = None, timeout: Optional[float] = None
    ) -> AsyncGenerator[Union[TokenDelta, ThinkingDelta, ToolExecutionUpdate, ForwarderResult], None]:
        cmd = self._build_command(prompt, conversation_id)
        logger.info(f"Forwarding prompt to agy CLI (conv_id={conversation_id})...")

        max_total_timeout = timeout or getattr(config, "forwarder_timeout", 900.0)
        inactivity_timeout = getattr(config, "inactivity_timeout", 300.0)
        start_time = asyncio.get_event_loop().time()
        last_activity_time = asyncio.get_event_loop().time()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        accumulated_text = []
        result_event: Optional[ForwarderResult] = None
        extracted_conv_id = conversation_id or ""

        try:
            while True:
                now = asyncio.get_event_loop().time()
                total_elapsed = now - start_time
                if total_elapsed >= max_total_timeout:
                    logger.warning(f"Max total timeout ({max_total_timeout}s) reached.")
                    raise asyncio.TimeoutError(f"Maximum execution ceiling of {int(max_total_timeout)}s reached.")

                inactivity_elapsed = now - last_activity_time
                remaining = max(1.0, inactivity_timeout - inactivity_elapsed)
                if inactivity_elapsed >= inactivity_timeout:
                    logger.warning(f"Inactivity timeout ({inactivity_timeout}s) reached.")
                    raise asyncio.TimeoutError(f"No response or tool activity detected for {int(inactivity_timeout)}s.")

                line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                if not line:
                    break

                # Output received from agy proves activity; reset inactivity timer
                last_activity_time = asyncio.get_event_loop().time()
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON line from agy: {line_str}")
                    continue

                evt_type = data.get("event")
                if evt_type == "init":
                    extracted_conv_id = data.get("conversation_id") or extracted_conv_id

                parsed = parse_ndjson_line(data)
                if parsed:
                    if isinstance(parsed, TokenDelta):
                        accumulated_text.append(parsed.text)
                        yield parsed
                    elif isinstance(parsed, (ThinkingDelta, ToolExecutionUpdate)):
                        yield parsed
                    elif isinstance(parsed, ForwarderResult):
                        result_event = parsed
                        yield parsed

            # Wait for process exit with short grace period
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass

            if proc.returncode != 0 and (not result_event or result_event.status != "SUCCESS"):
                stderr_bytes = b""
                try:
                    stderr_bytes = await asyncio.wait_for(proc.stderr.read(), timeout=3.0)
                except Exception:
                    pass
                err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
                logger.error(f"agy CLI failed with code {proc.returncode}: {err_msg}")
                if not result_event:
                    result_event = ForwarderResult(
                        conversation_id=extracted_conv_id,
                        status="ERROR",
                        response="".join(accumulated_text),
                        error=err_msg or f"Process exited with code {proc.returncode}",
                    )
                    yield result_event

            elif not result_event:
                # Process completed successfully but didn't emit final result event
                result_event = ForwarderResult(
                    conversation_id=extracted_conv_id,
                    status="SUCCESS",
                    response="".join(accumulated_text),
                )
                yield result_event

        except asyncio.TimeoutError as te:
            now = asyncio.get_event_loop().time()
            elapsed = int(now - start_time)
            err_msg = str(te).strip() if str(te).strip() else f"Execution timed out after {elapsed} seconds."
            logger.error(f"agy CLI execution timed out after {elapsed}s: {err_msg}")
            try:
                proc.terminate()
                await asyncio.sleep(0.5)
                if proc.returncode is None:
                    proc.kill()
            except Exception:
                pass
            if not result_event:
                yield ForwarderResult(
                    conversation_id=extracted_conv_id,
                    status="TIMEOUT",
                    response="".join(accumulated_text),
                    error=err_msg,
                )

        except asyncio.CancelledError:
            try:
                proc.terminate()
                await asyncio.sleep(0.5)
                if proc.returncode is None:
                    proc.kill()
            except Exception:
                pass
            raise
        except Exception as e:
            logger.error(f"Error in forward_stream: {e}")
            if not result_event:
                yield ForwarderResult(
                    conversation_id=extracted_conv_id,
                    status="ERROR",
                    response="".join(accumulated_text),
                    error=str(e),
                )
