import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console

from tools.mcp_client import MCPClientManager
from agent.react import ReActAgent

console = Console()

async def main():
    load_dotenv()
    console.print("[bold green]Starting AI Agent...[/bold green]")
    
    console.print("Initializing MCP Client Manager...")
    mcp_client = MCPClientManager()
    
    console.print("Launching Internal MCP Server for Memory & Skills...")
    try:
        await mcp_client.connect_to_server("internal", "python", ["mcp_server.py"])
        console.print("[green]Connected to Internal MCP memory.[/green]")
    except Exception as e:
        console.print(f"[red]Failed to start internal MCP server: {e}[/red]")
        return
        
    # Optional: uncomment to connect to an MCP server
    # try:
    #     await mcp_client.connect_to_server("filesystem", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "./"])
    #     console.print("[green]Connected to filesystem MCP.[/green]")
    # except Exception as e:
    #     console.print(f"[yellow]Could not connect to filesystem MCP: {e}[/yellow]")
    
    import os
    model_name = os.getenv("LITELLM_MODEL", "ollama/gemma4:e4b")
    api_base = os.getenv("LITELLM_API_BASE", "http://localhost:11434")
    api_key = os.getenv("LITELLM_API_KEY", "")
    agent = ReActAgent(mcp_client, model_name=model_name, api_base=api_base, api_key=api_key)
    
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
