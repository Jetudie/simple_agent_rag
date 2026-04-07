import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console

from memory.manager import MemoryManager
from tools.mcp_client import MCPClientManager
from agent.react import ReActAgent

console = Console()

async def main():
    load_dotenv()
    console.print("[bold green]Starting AI Agent...[/bold green]")
    
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[yellow]WARNING: GEMINI_API_KEY not found in environment. Please add it to your .env file.[/yellow]")
    
    console.print("Initializing Memory Manager (VectorRAG + GraphRAG)...")
    memory_manager = MemoryManager(model_name="gemini/gemini-2.5-pro")
    
    console.print("Initializing MCP Client Manager...")
    mcp_client = MCPClientManager()
    
    # Optional: uncomment to connect to an MCP server
    # Note: Requires npx and nodejs installed.
    # try:
    #     await mcp_client.connect_to_server("filesystem", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "./"])
    #     console.print("[green]Connected to filesystem MCP.[/green]")
    # except Exception as e:
    #     console.print(f"[yellow]Could not connect to filesystem MCP: {e}[/yellow]")
    
    agent = ReActAgent(memory_manager, mcp_client, model_name="gemini/gemini-2.5-pro")
    
    console.print("\n[bold blue]Agent Ready![/bold blue] Type 'exit' to quit.")
    
    try:
        while True:
            # Synchronous input in CLI loop
            user_input = console.input("\n[bold]You:[/bold] ")
            if user_input.lower() in ['exit', 'quit']:
                break
                
            console.print("\n[italic yellow]Agent is processing...[/italic yellow]")
            answer = await agent.process_user_query(user_input)
            
            console.print(f"\n[bold magenta]Final Answer:[/bold magenta]\n{answer}")
            
    finally:
        console.print("\nCleaning up resources...")
        await mcp_client.cleanup()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Exiting...[/bold red]")
