#!/usr/bin/env python3
"""Mascarade Control TUI — System control and management interface."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

# Configuration
CONFIG_PATH = Path("~/.mascarade/control_config.json").expanduser()
LOG_DIR = Path("~/.mascarade/logs").expanduser()
DEFAULT_API_URL = "http://localhost:8100"

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=LOG_DIR / "control.log",
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger("mascarade.control")


class APIClient:
    """HTTP client for Mascarade API with control capabilities."""
    
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
                return {"error": str(e), "status": e.response.status_code}
            except Exception as e:
                logger.error("Request failed: %s", str(e))
                return {"error": str(e)}


class ControlSystem:
    """Core control system for Mascarade."""
    
    def __init__(self, api_client: APIClient):
        self.api = api_client
    
    async def get_system_info(self) -> Dict:
        """Get system information."""
        return await self.api.request("GET", "/health")
    
    async def list_agents(self) -> Dict:
        """List all registered agents."""
        return await self.api.request("GET", "/v1/api/agents")
    
    async def get_agent_detail(self, agent_name: str) -> Dict:
        """Get detailed information about an agent."""
        return await self.api.request("GET", f"/v1/api/v1/agents/{agent_name}")
    
    async def enable_agent(self, agent_name: str) -> Dict:
        """Enable an agent."""
        return await self.api.request("PUT", f"/v1/api/agents/{agent_name}", json={"enabled": True})
    
    async def disable_agent(self, agent_name: str) -> Dict:
        """Disable an agent."""
        return await self.api.request("PUT", f"/v1/api/agents/{agent_name}", json={"enabled": False})
    
    async def list_providers(self) -> Dict:
        """List all LLM providers."""
        return await self.api.request("GET", "/v1/api/providers")
    
    async def set_provider_key(self, provider: str, api_key: str) -> Dict:
        """Set API key for a provider."""
        return await self.api.request(
            "PUT", 
            f"/v1/api/providers/{provider}/key",
            json={"api_key": api_key}
        )
    
    async def clear_cache(self) -> Dict:
        """Clear all caches."""
        return await self.api.request("POST", "/cache/reset")
    
    async def restart_p2p(self) -> Dict:
        """Restart P2P mesh."""
        return await self.api.request("POST", "/v1/api/scheduler/workers/restart")
    
    async def get_finetune_jobs(self) -> Dict:
        """List fine-tuning jobs."""
        return await self.api.request("GET", "/v1/api/finetune/jobs")
    
    async def create_finetune_job(self, config: Dict) -> Dict:
        """Create a new fine-tuning job."""
        return await self.api.request("POST", "/v1/api/finetune/jobs", json=config)


class ControlTUI:
    """Text User Interface for system control."""
    
    def __init__(self, control: ControlSystem):
        self.control = control
        self.console = Console()
        self.running = True
    
    def render_header(self) -> Panel:
        """Render header panel."""
        header_text = Text("🎛️ Mascarade Control Center", style="bold magenta")
        header_text += Text(" — System Management Interface", style="dim")
        return Panel(header_text, style="magenta")
    
    def render_main_menu(self) -> None:
        """Render main menu."""
        self.console.clear()
        self.console.print(self.render_header())
        
        menu = Table(title="Main Menu", show_header=False, box=None)
        menu.add_column("Option", style="cyan")
        menu.add_column("Description", style="white")
        
        menu.add_row("1", "Agent Management")
        menu.add_row("2", "Provider Configuration")
        menu.add_row("3", "System Operations")
        menu.add_row("4", "Fine-Tuning Jobs")
        menu.add_row("5", "View System Info")
        menu.add_row("Q", "Quit")
        
        self.console.print(menu)
    
    async def agent_management_menu(self) -> None:
        """Agent management interface."""
        while True:
            self.console.clear()
            self.console.print(self.render_header())
            self.console.print(Panel.fit("🤖 Agent Management", style="yellow"))
            
            # List agents
            agents = await self.control.list_agents()
            if "error" in agents:
                self.console.print(f"[red]Error: {agents['error']}[/red]")
                break
            
            table = Table(title="Registered Agents", box=None)
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Type", style="blue")
            
            for i, agent in enumerate(agents.get("agents", []), 1):
                status = "✓ Active" if agent.get("enabled", False) else "✗ Disabled"
                table.add_row(str(i), agent["name"], status, agent.get("type", "standard"))
            
            self.console.print(table)
            self.console.print("\n[bold]Actions:[/bold] [E]nable | [D]isable | [B]ack")
            
            choice = Prompt.ask("Select agent ID or action").strip().lower()
            
            if choice == "b":
                break
            elif choice == "e":
                agent_id = Prompt.ask("Enter agent ID to enable")
                try:
                    agent_name = agents["agents"][int(agent_id)-1]["name"]
                    result = await self.control.enable_agent(agent_name)
                    if "error" not in result:
                        self.console.print(f"[green]✓ Agent {agent_name} enabled[/green]")
                    else:
                        self.console.print(f"[red]✗ Error: {result['error']}[/red]")
                except Exception as e:
                    self.console.print(f"[red]✗ Error: {e}[/red]")
                await asyncio.sleep(2)
            elif choice == "d":
                agent_id = Prompt.ask("Enter agent ID to disable")
                try:
                    agent_name = agents["agents"][int(agent_id)-1]["name"]
                    result = await self.control.disable_agent(agent_name)
                    if "error" not in result:
                        self.console.print(f"[yellow]⚠️ Agent {agent_name} disabled[/yellow]")
                    else:
                        self.console.print(f"[red]✗ Error: {result['error']}[/red]")
                except Exception as e:
                    self.console.print(f"[red]✗ Error: {e}[/red]")
                await asyncio.sleep(2)
    
    async def provider_config_menu(self) -> None:
        """Provider configuration interface."""
        while True:
            self.console.clear()
            self.console.print(self.render_header())
            self.console.print(Panel.fit("🔌 Provider Configuration", style="cyan"))
            
            # List providers
            providers = await self.control.list_providers()
            if "error" in providers:
                self.console.print(f"[red]Error: {providers['error']}[/red]")
                break
            
            table = Table(title="LLM Providers", box=None)
            table.add_column("Provider", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Key Configured", style="blue")
            
            for provider, info in providers.get("providers", {}).items():
                key_status = "✓ Yes" if info.get("api_key_configured") else "✗ No"
                status = "✓ Healthy" if info.get("healthy") else "✗ Unhealthy"
                table.add_row(provider, status, key_status)
            
            self.console.print(table)
            self.console.print("\n[bold]Actions:[/bold] [S]et API Key | [B]ack")
            
            choice = Prompt.ask("Select provider or action").strip().lower()
            
            if choice == "b":
                break
            elif choice == "s":
                provider = Prompt.ask("Enter provider name")
                api_key = Prompt.ask("Enter API key", password=True)
                result = await self.control.set_provider_key(provider, api_key)
                if "error" not in result:
                    self.console.print(f"[green]✓ API key set for {provider}[/green]")
                else:
                    self.console.print(f"[red]✗ Error: {result['error']}[/red]")
                await asyncio.sleep(2)
    
    async def system_ops_menu(self) -> None:
        """System operations interface."""
        while True:
            self.console.clear()
            self.console.print(self.render_header())
            self.console.print(Panel.fit("⚙️ System Operations", style="red"))
            
            table = Table(title="Available Operations", show_header=False, box=None)
            table.add_column("Option", style="cyan")
            table.add_column("Description", style="white")
            
            table.add_row("1", "Clear All Caches")
            table.add_row("2", "Restart P2P Mesh")
            table.add_row("3", "View System Logs")
            table.add_row("B", "Back to Main Menu")
            
            self.console.print(table)
            
            choice = Prompt.ask("Select operation").strip().lower()
            
            if choice == "b":
                break
            elif choice == "1":
                if Confirm.ask("⚠️ Are you sure you want to clear all caches?"):
                    result = await self.control.clear_cache()
                    if "error" not in result:
                        self.console.print("[green]✓ All caches cleared[/green]")
                    else:
                        self.console.print(f"[red]✗ Error: {result['error']}[/red]")
                    await asyncio.sleep(2)
            elif choice == "2":
                if Confirm.ask("⚠️ Are you sure you want to restart P2P mesh?"):
                    result = await self.control.restart_p2p()
                    if "error" not in result:
                        self.console.print("[green]✓ P2P mesh restart initiated[/green]")
                    else:
                        self.console.print(f"[red]✗ Error: {result['error']}[/red]")
                    await asyncio.sleep(2)
            elif choice == "3":
                self.console.print("📄 Log viewing not yet implemented")
                await asyncio.sleep(2)
    
    async def finetune_menu(self) -> None:
        """Fine-tuning jobs interface."""
        while True:
            self.console.clear()
            self.console.print(self.render_header())
            self.console.print(Panel.fit("🔬 Fine-Tuning Jobs", style="blue"))
            
            # List jobs
            jobs = await self.control.get_finetune_jobs()
            if "error" in jobs:
                self.console.print(f"[red]Error: {jobs['error']}[/red]")
                break
            
            table = Table(title="Fine-Tuning Jobs", box=None)
            table.add_column("Job ID", style="cyan")
            table.add_column("Model", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Created", style="dim")
            
            for job in jobs.get("jobs", []):
                table.add_row(
                    job.get("job_id", "N/A"),
                    job.get("base_model", "N/A"),
                    job.get("status", "unknown"),
                    job.get("created_at", "N/A")
                )
            
            self.console.print(table)
            self.console.print("\n[bold]Actions:[/bold] [C]reate Job | [B]ack")
            
            choice = Prompt.ask("Select action").strip().lower()
            
            if choice == "b":
                break
            elif choice == "c":
                self.console.print("🔧 Job creation not yet implemented")
                await asyncio.sleep(2)
    
    async def show_system_info(self) -> None:
        """Display system information."""
        self.console.clear()
        self.console.print(self.render_header())
        self.console.print(Panel.fit("📊 System Information", style="green"))
        
        info = await self.control.get_system_info()
        if "error" in info:
            self.console.print(f"[red]Error: {info['error']}[/red]")
            return
        
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="dim")
        table.add_column("Value", style="white")
        
        info_items = [
            ("Status", info.get("status", "unknown")),
            ("Version", info.get("version", "N/A")),
            ("Uptime", info.get("uptime", "N/A")),
            ("API URL", self.control.api.base_url),
            ("API Key", "✓ Configured" if self.control.api.api_key else "✗ Not set"),
        ]
        
        for label, value in info_items:
            table.add_row(label, str(value))
        
        self.console.print(table)
        self.console.print("\n[Press any key to continue...]")
        Prompt.ask("")
    
    async def run(self) -> None:
        """Main control loop."""
        while self.running:
            self.render_main_menu()
            
            choice = Prompt.ask("\nSelect option", default="1").strip().lower()
            
            if choice == "q":
                self.running = False
            elif choice == "1":
                await self.agent_management_menu()
            elif choice == "2":
                await self.provider_config_menu()
            elif choice == "3":
                await self.system_ops_menu()
            elif choice == "4":
                await self.finetune_menu()
            elif choice == "5":
                await self.show_system_info()
            else:
                self.console.print("[red]Invalid option[/red]")
                await asyncio.sleep(1)


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
    control = ControlSystem(api_client)
    tui = ControlTUI(control)
    
    # Start control interface
    logger.info("Starting Mascarade Control TUI")
    try:
        await tui.run()
    except KeyboardInterrupt:
        logger.info("Control interface stopped by user")
    except Exception as e:
        logger.error("Fatal error: %s", str(e), exc_info=True)
        raise
    finally:
        logger.info("Control session ended")


if __name__ == "__main__":
    asyncio.run(main())
