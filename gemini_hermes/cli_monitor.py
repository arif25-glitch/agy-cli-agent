"""
Interactive Terminal UI Dashboard for Gemini-Hermes (./run.sh monitor).
Displays real-time daemon telemetry, active tasks, Jev System-One accelerator stats,
task queue depth, and rolling live log stream using the 'rich' library.
"""
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gemini_hermes.config import BASE_DIR, SESSIONS_DIR, config
from gemini_hermes.memory.session_store import SessionStore
from gemini_hermes.telemetry import TelemetryExporter

PID_FILE = BASE_DIR / "gemini-hermes.pid"
LOG_FILE = BASE_DIR / "gemini-hermes.log"


def format_token_count(n: int) -> str:
    """Format token count with clean human-readable thousands and millions suffixes."""
    try:
        val = int(n)
    except (ValueError, TypeError):
        val = 0
    if val >= 1_000_000:
        return f"{val:,} ({val/1_000_000:.2f}M)"
    elif val >= 1_000:
        return f"{val:,} ({val/1_000:.1f}k)"
    return f"{val:,}"


class CliMonitor:
    """Terminal Dashboard Controller."""

    def __init__(self, refresh_rate: float = 1.0):
        self.console = Console()
        self.refresh_rate = refresh_rate
        self.running = True
        self.session_store = SessionStore(SESSIONS_DIR)

    def get_daemon_status(self) -> Dict[str, Any]:
        """Check PID file and process health."""
        if not PID_FILE.exists():
            return {"running": False, "pid": None, "uptime": "0s"}
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process is alive
            os.kill(pid, 0)
            # Process is alive, compute uptime from PID file mtime
            mtime = PID_FILE.stat().st_mtime
            uptime_sec = int(time.time() - mtime)
            mins, secs = divmod(uptime_sec, 60)
            hours, mins = divmod(mins, 60)
            uptime_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"
            return {"running": True, "pid": pid, "uptime": uptime_str}
        except (ValueError, OSError):
            return {"running": False, "pid": None, "uptime": "0s"}

    def get_recent_logs(self, max_lines: int = 6) -> List[str]:
        """Read recent non-empty lines from gemini-hermes.log."""
        if not LOG_FILE.exists():
            return ["[dim]No log file found.[/dim]"]
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            recent = [line.strip() for line in lines if line.strip()][-max_lines:]
            return recent or ["[dim]Log file is empty.[/dim]"]
        except Exception as e:
            return [f"[red]Error reading logs: {e}[/red]"]

    def build_header(self, daemon_info: Dict[str, Any]) -> Panel:
        """Render top navigation header."""
        is_up = daemon_info["running"]
        status_color = "bold green" if is_up else "bold red"
        status_label = "● ONLINE" if is_up else "○ STOPPED"
        pid_label = f"PID: {daemon_info['pid']}" if daemon_info["pid"] else "PID: N/A"

        header_text = Text()
        header_text.append("🪐 GEMINI-HERMES LIVE MONITOR  ", style="bold cyan")
        header_text.append(f"[{status_label}]  ", style=status_color)
        header_text.append(f"{pid_label}  |  Uptime: {daemon_info['uptime']}  |  ", style="dim white")
        header_text.append(time.strftime("%H:%M:%S"), style="bold yellow")

        return Panel(header_text, style="cyan", border_style="bright_blue")

    def build_core_panel(self, state: Dict[str, Any], daemon_info: Dict[str, Any]) -> Panel:
        """Render bot core telemetry."""
        table = Table(box=None, expand=True, show_header=False, pad_edge=False)
        table.add_column("Key", style="bold white", width=18)
        table.add_column("Val", style="cyan")

        table.add_row("Execution Engine:", "Google Antigravity CLI (agy)")
        table.add_row("Architecture:", "Dual-World Decoupled (Pure Core & Jev)")
        current_model = state.get("selected_model") or getattr(config, "agy_model", "gemini-3.7-flash")
        table.add_row("Active Model:", f"[bold cyan]{current_model}[/bold cyan]")
        table.add_row("Configured Effort:", f"{config.reasoning_effort.upper()} (Default)")

        active_chat = state.get("active_chat_id")
        table.add_row("Active Chat ID:", str(active_chat) if active_chat else "[dim]Idle (No active turn)[/dim]")
        
        status_step = state.get("active_step") or ("Running" if daemon_info["running"] else "Offline")
        table.add_row("Engine State:", f"[green]{status_step}[/green]" if daemon_info["running"] else "[red]Offline[/red]")

        return Panel(table, title="[bold]🤖 Core Engine Telemetry[/bold]", border_style="blue")

    def build_jev_panel(self, state: Dict[str, Any]) -> Panel:
        """Render Jev System-One accelerator telemetry."""
        jev_info = state.get("jev", {})
        is_jev_active = jev_info.get("enabled", getattr(config, "jev_enabled", False))

        table = Table(box=None, expand=True, show_header=False, pad_edge=False)
        table.add_column("Key", style="bold white", width=18)
        table.add_column("Val", style="magenta")

        if is_jev_active:
            status_text = "[bold green]ONLINE[/bold green] (accelerator active)"
            timeout_str = f"{getattr(config, 'jev_timeout', 3.0)}s guard"
            latency = jev_info.get("latency_ms")
            latency_str = f"{latency}ms" if latency else "Ready"
            complexity = jev_info.get("complexity")
            comp_str = f"{complexity:.2f} / 2.0" if complexity is not None else "Awaiting next turn"
            last_dec = jev_info.get("last_decision") or "Standard"
        else:
            status_text = "[dim yellow]STANDBY[/dim yellow] (pure engine mode)"
            timeout_str = "N/A"
            latency_str = "N/A"
            comp_str = "N/A"
            last_dec = "Pure Core Heuristics"

        table.add_row("Accelerator:", status_text)
        table.add_row("Timeout Limit:", timeout_str)
        table.add_row("Last Reflex Latency:", latency_str)
        table.add_row("Cognitive Complexity:", comp_str)
        table.add_row("Effort Selector:", f"[bold cyan]{last_dec.upper()}[/bold cyan]")
        table.add_row("/btw Sidecar Classifier:", "[green]Smart Jev Choice[/green]" if is_jev_active else "[yellow]Pure Regex/Keywords[/yellow]")

        return Panel(table, title="[bold]⚡ TypeSafe AI (Jev) System-One[/bold]", border_style="magenta")

    def build_task_and_queue_panel(self, state: Dict[str, Any]) -> Panel:
        """Render active turn progress and FIFO queue state."""
        table = Table(box=None, expand=True, show_header=False, pad_edge=False)
        table.add_column("Key", style="bold white", width=18)
        table.add_column("Val")

        preview = state.get("active_task_preview")
        elapsed = state.get("active_task_elapsed", 0.0)
        effort = state.get("reasoning_effort", config.reasoning_effort)
        is_fp = state.get("is_fast_path", False)
        q_depth = state.get("queue_depth", 0)
        q_items = state.get("queue_items", [])

        if preview:
            table.add_row("Ongoing Task:", f"[yellow]{preview}[/yellow]")
            fp_tag = " [bold green](Fast Reflex: 0 thinking tokens)[/bold green]" if is_fp else ""
            selected_model = state.get("selected_model") or getattr(config, "agy_model", "gemini-3.7-flash")
            table.add_row("Active Model:", f"[bold cyan]{selected_model}[/bold cyan] ({effort.upper()}){fp_tag}")
            table.add_row("Elapsed Time:", f"{elapsed}s")
        else:
            table.add_row("Ongoing Task:", "[dim green]System Idle — Ready for requests[/dim green]")

        q_label = f"[bold green]{q_depth} / 10[/bold green]" if q_depth == 0 else f"[bold yellow]{q_depth} / 10 pending[/bold yellow]"
        table.add_row("Task Queue Depth:", q_label)
        if q_items:
            items_str = ", ".join([f"#{i+1}: {item[:25]}" for i, item in enumerate(q_items[:3])])
            table.add_row("Queue Preview:", f"[dim]{items_str}[/dim]")
        else:
            table.add_row("Queue Preview:", "[dim]Queue empty (Zero dropped messages)[/dim]")

        return Panel(table, title="[bold]📋 Execution & Task Queue[/bold]", border_style="green")

    def build_token_usage_panel(self, state: Dict[str, Any]) -> Panel:
        """Render token usage metrics for current session and global lifetime."""
        tokens_info = state.get("tokens", {})
        session_tok = tokens_info.get("session") or {}
        global_tok = tokens_info.get("global") or {}

        # Fallback to direct disk inspection if state is unpopulated
        if not session_tok or not global_tok:
            try:
                active_chat = state.get("active_chat_id")
                session_tok = self.session_store.get_session_token_usage(active_chat)
                global_tok = self.session_store.get_total_token_usage()
            except Exception:
                pass

        table = Table(box=None, expand=True, show_header=False, pad_edge=False)
        table.add_column("Key", style="bold white", width=18)
        table.add_column("Val", style="yellow")

        # Session Metrics
        active_chat = session_tok.get("chat_id")
        chat_label = str(active_chat) if active_chat else "[dim]Latest Session[/dim]"
        sess_in = session_tok.get("input_tokens") if "input_tokens" in session_tok else session_tok.get("total_input_tokens", 0)
        sess_out = session_tok.get("output_tokens") if "output_tokens" in session_tok else session_tok.get("total_output_tokens", 0)
        sess_total = session_tok.get("total_tokens", sess_in + sess_out)
        sess_turns = session_tok.get("turn_count", 0)

        # Global Lifetime Metrics
        glob_in = global_tok.get("total_input_tokens", 0)
        glob_out = global_tok.get("total_output_tokens", 0)
        glob_total = global_tok.get("total_tokens", glob_in + glob_out)
        glob_sessions = global_tok.get("session_count", 0)
        glob_turns = global_tok.get("total_turns", 0)

        table.add_row("Session Chat:", chat_label)
        table.add_row(
            "Session In / Out:",
            f"{format_token_count(sess_in)} in  /  {format_token_count(sess_out)} out",
        )
        table.add_row(
            "Session Total:",
            f"[bold yellow]{format_token_count(sess_total)}[/bold yellow] ({sess_turns} turns)",
        )
        table.add_row(
            "Tracked Sessions:",
            f"[cyan]{glob_sessions} active sessions[/cyan] ({glob_turns} turns)",
        )
        table.add_row(
            "Global In / Out:",
            f"{format_token_count(glob_in)} in  /  {format_token_count(glob_out)} out",
        )
        table.add_row(
            "Lifetime Total:",
            f"[bold green]{format_token_count(glob_total)} tokens[/bold green]",
        )

        return Panel(table, title="[bold]📊 Token & Session Usage[/bold]", border_style="yellow")

    def build_logs_panel(self) -> Panel:
        """Render recent log stream."""
        logs = self.get_recent_logs(max_lines=5)
        log_text = Text()
        for line in logs:
            if "ERROR" in line or "Exception" in line:
                log_text.append(f"{line}\n", style="bold red")
            elif "WARNING" in line:
                log_text.append(f"{line}\n", style="yellow")
            elif "Jev dynamic effort" in line or "fast-path" in line:
                log_text.append(f"{line}\n", style="bold cyan")
            elif "Forwarding prompt" in line:
                log_text.append(f"{line}\n", style="green")
            else:
                log_text.append(f"{line}\n", style="dim white")

        return Panel(log_text, title="[bold]📜 Live Tail (gemini-hermes.log)[/bold]", border_style="white")

    def render_dashboard(self) -> Layout:
        """Compose the full dashboard layout."""
        daemon_info = self.get_daemon_status()
        state = TelemetryExporter.read_state()

        layout = Layout()
        layout.split_column(
            Layout(self.build_header(daemon_info), size=3),
            Layout(name="body", ratio=1),
            Layout(self.build_logs_panel(), size=7),
            Layout(
                Text("  [Ctrl+C] Exit Dashboard  |  [./run.sh logs] View Raw Log Stream", style="dim yellow"),
                size=1,
            ),
        )

        layout["body"].split_row(
            Layout(
                Group(
                    self.build_core_panel(state, daemon_info),
                    self.build_task_and_queue_panel(state),
                ),
                ratio=1,
            ),
            Layout(
                Group(
                    self.build_jev_panel(state),
                    self.build_token_usage_panel(state),
                ),
                ratio=1,
            ),
        )

        return layout

    def run(self):
        """Run live refresh loop."""
        self.console.clear()
        try:
            with Live(self.render_dashboard(), console=self.console, refresh_per_second=2, screen=True) as live:
                while self.running:
                    live.update(self.render_dashboard())
                    time.sleep(self.refresh_rate)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Dashboard closed.[/yellow]")


def run_monitor():
    """Entry point for CLI monitor."""
    monitor = CliMonitor()
    monitor.run()


if __name__ == "__main__":
    run_monitor()
