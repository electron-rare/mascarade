#!/usr/bin/env python3
"""Mascarade Monitoring TUI — Real-time system monitoring and control."""

import asyncio
import curses
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Configuration
CONFIG_PATH = Path("~/.mascarade/monitor_config.json").expanduser()
LOG_DIR = Path("~/.mascarade/logs").expanduser()
DEFAULT_API_URL = "http://localhost:8100"

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=LOG_DIR / "monitor.log",
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger("mascarade.monitor")


class APIClient:
    """HTTP client for Mascarade API."""
    
    def __init__(self, base_url: str = DEFAULT_API_URL, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make API request with error handling."""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(headers=self.headers) as client:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("API error: %s %s", e.response.status_code, e.response.text)
                return {"error": str(e)}
            except Exception as e:
                logger.error("Request failed: %s", str(e))
                return {"error": str(e)}


class SystemMonitor:
    """Core monitoring system."""
    
    def __init__(self, api_client: APIClient):
        self.api = api_client
        self.metrics_history: Dict[str, List[float]] = {}
        self.start_time = time.time()
    
    async def get_system_status(self) -> Dict:
        """Get overall system status."""
        return await self.api.request("GET", "/health")
    
    async def get_provider_status(self) -> Dict:
        """Get LLM provider status."""
        return await self.api.request("GET", "/v1/api/providers/status")
    
    async def get_agent_status(self) -> Dict:
        """Get agent registry status."""
        return await self.api.request("GET", "/v1/api/agents")
    
    async def get_cache_stats(self) -> Dict:
        """Get cache performance metrics."""
        return await self.api.request("GET", "/cache/stats")
    
    async def get_p2p_status(self) -> Dict:
        """Get P2P mesh status."""
        return await self.api.request("GET", "/v1/api/scheduler/status")
    
    async def collect_metrics(self) -> Dict:
        """Collect all metrics for dashboard."""
        results = await asyncio.gather(
            self.get_system_status(),
            self.get_provider_status(),
            self.get_agent_status(),
            self.get_cache_stats(),
            self.get_p2p_status(),
        )
        
        return {
            "system": results[0],
            "providers": results[1],
            "agents": results[2],
            "cache": results[3],
            "p2p": results[4],
            "timestamp": datetime.now().isoformat(),
        }


class TUI:
    """Text User Interface for monitoring."""
    
    def __init__(self, monitor: SystemMonitor):
        self.monitor = monitor
        self.console = Console()
        self.running = True
        self.refresh_interval = 2.0
    
    def render_header(self) -> Panel:
        """Render header panel."""
        header_text = Text("🎭 Mascarade Monitoring Dashboard", style="bold cyan")
        header_text += Text(f" — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        return Panel(header_text, style="blue")
    
    def render_system_status(self, data: Dict) -> Panel:
        """Render system status panel."""
        table = Table(show_header=False, box=None)
        table.add_column(style="dim", width=20)
        table.add_column(style="green")
        
        status_items = [
            ("Status", data.get("status", "unknown")),
            ("Uptime", data.get("uptime", "N/A")),
            ("Version", data.get("version", "N/A")),
            ("API Key", "✓ Configured" if self.monitor.api.api_key else "✗ Not set"),
        ]
        
        for label, value in status_items:
            table.add_row(label, str(value))
        
        return Panel(table, title="System Status", border_style="green")
    
    def render_providers(self, data: Dict) -> Panel:
        """Render provider status panel."""
        table = Table(title="LLM Providers", box=None)
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Latency", style="magenta")
        table.add_column("Requests", style="blue")
        
        for provider, info in data.get("providers", {}).items():
            status_style = "green" if info.get("healthy") else "red"
            table.add_row(
                provider,
                Text(info.get("status", "unknown"), style=status_style),
                f"{info.get('avg_latency_ms', 0)}ms",
                str(info.get("request_count", 0)),
            )
        
        return Panel(table, border_style="cyan")
    
    def render_agents(self, data: Dict) -> Panel:
        """Render agent status panel."""
        table = Table(title="Agents", box=None)
        table.add_column("Name", style="yellow")
        table.add_column("Type", style="blue")
        table.add_column("Status", style="green")
        
        for agent in data.get("agents", [])[:10]:  # Top 10 agents
            table.add_row(
                agent.get("name", "unknown"),
                agent.get("type", "standard"),
                "✓ Active" if agent.get("enabled", False) else "✗ Inactive",
            )
        
        return Panel(table, border_style="yellow")
    
    def render_cache(self, data: Dict) -> Panel:
        """Render cache statistics panel."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="magenta")
        
        cache_items = [
            ("Hit Rate", f"{data.get('hit_rate', 0):.1%}"),
            ("Miss Rate", f"{data.get('miss_rate', 0):.1%}"),
            ("Total Requests", str(data.get("total_requests", 0))),
            ("Cache Size", f"{data.get('current_size', 0)} items"),
        ]
        
        for label, value in cache_items:
            table.add_row(label, value)
        
        return Panel(table, title="Cache Performance", border_style="magenta")
    
    def render_p2p(self, data: Dict) -> Panel:
        """Render P2P mesh status panel."""
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="blue")
        
        p2p_items = [
            ("Nodes", str(data.get("node_count", 0))),
            ("Tasks Queue", str(data.get("queued_tasks", 0))),
            ("Active Tasks", str(data.get("active_tasks", 0))),
            ("Mesh Status", data.get("status", "unknown")),
        ]
        
        for label, value in p2p_items:
            table.add_row(label, value)
        
        return Panel(table, title="P2P Mesh", border_style="blue")
    
    def render_footer(self) -> Panel:
        """Render footer with controls."""
        controls = Text("Controls: [Q]uit | [R]efresh | [L]ogs | [S]ettings")
        return Panel(controls, style="dim")
    
    async def render_dashboard(self):
        """Main rendering loop."""
        while self.running:
            try:
                metrics = await self.monitor.collect_metrics()
                
                # Create dashboard layout
                dashboard = Table.grid(padding=1)
                dashboard.add_row(self.render_header())
                dashboard.add_row(
                    self.render_system_status(metrics["system"]),
                    self.render_cache(metrics["cache"]),
                )
                dashboard.add_row(
                    self.render_providers(metrics["providers"]),
                    self.render_p2p(metrics["p2p"]),
                )
                dashboard.add_row(self.render_agents(metrics["agents"]))
                dashboard.add_row(self.render_footer())
                
                # Display with Rich
                with Live(dashboard, refresh_per_second=4, screen=True) as live:
                    while self.running and live.is_active:
                        await asyncio.sleep(self.refresh_interval)
                        metrics = await self.monitor.collect_metrics()
                        # Update panels with new data
                        # (Implementation would update each panel with fresh data)
                        await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Dashboard error: %s", str(e))
                self.console.print(f"[red]Error: {e}[/red]")
                await asyncio.sleep(2)


class LogManager:
    """Manage monitoring logs."""
    
    def __init__(self, log_dir: Path = LOG_DIR):
        self.log_dir = log_dir
    
    def get_log_files(self) -> List[Path]:
        """Get list of log files."""
        return sorted(self.log_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    def read_log(self, log_file: Path, lines: int = 100) -> str:
        """Read last N lines of log file."""
        try:
            with open(log_file, "r") as f:
                return "\n".join(f.readlines()[-lines:])
        except Exception as e:
            logger.error("Failed to read log: %s", str(e))
            return f"Error reading log: {e}"
    
    def clear_old_logs(self, days: int = 30):
        """Clear logs older than N days."""
        cutoff = time.time() - (days * 86400)
        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff:
                log_file.unlink()
                logger.info("Deleted old log: %s", log_file.name)


async def main():
    """Main entry point."""
    # Load configuration
    config = {"api_url": DEFAULT_API_URL, "api_key": None}
    if CONFIG_PATH.exists():
        try:
            config.update(json.loads(CONFIG_PATH.read_text()))
        except Exception as e:
            logger.error("Failed to load config: %s", str(e))
    
    # Initialize components
    api_client = APIClient(base_url=config["api_url"], api_key=config["api_key"])
    monitor = SystemMonitor(api_client)
    tui = TUI(monitor)
    log_manager = LogManager()
    
    # Start monitoring
    logger.info("Starting Mascarade Monitoring TUI")
    try:
        await tui.render_dashboard()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error("Fatal error: %s", str(e), exc_info=True)
        raise
    finally:
        logger.info("Monitoring session ended")


if __name__ == "__main__":
    asyncio.run(main())
