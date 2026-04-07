import asyncio
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import contextlib

class MCPClientManager:
    def __init__(self):
        self.servers: Dict[str, dict] = {}
        self._exit_stack = contextlib.AsyncExitStack()
        
    async def connect_to_server(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        server_parameters = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        
        # We need an asynchronous context stack to keep transports and sessions alive
        transport_context = stdio_client(server_parameters)
        read, write = await self._exit_stack.enter_async_context(transport_context)
        
        session = ClientSession(read, write)
        await self._exit_stack.enter_async_context(session)
        
        await session.initialize()
        
        self.servers[name] = {"session": session}
        print(f"Connected to MCP server: {name}")

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        all_tools = []
        for server_name, server_data in self.servers.items():
            session: ClientSession = server_data["session"]
            try:
                tools_response = await session.list_tools()
                for tool in tools_response.tools:
                    all_tools.append({
                        "server": server_name,
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    })
            except Exception as e:
                print(f"Error fetching tools from {server_name}: {e}")
        return all_tools
        
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        if server_name not in self.servers:
            return f"Error: Server {server_name} not found."
            
        session: ClientSession = self.servers[server_name]["session"]
        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            if hasattr(result, 'content') and result.content:
                text_results = []
                for content_block in result.content:
                    if hasattr(content_block, 'text'):
                        text_results.append(content_block.text)
                return "\n".join(text_results)
            elif getattr(result, 'isError', False):
                return f"Tool Execution Error."
            return "Tool executed successfully but returned no text."
        except Exception as e:
            return f"Tool Execution Exception: {str(e)}"
            
    async def cleanup(self):
        await self._exit_stack.aclose()
