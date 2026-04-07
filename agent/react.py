import json
import re
from typing import List, Dict, Any, Optional
from litellm import acompletion
from memory.manager import MemoryManager
from tools.mcp_client import MCPClientManager

SYSTEM_PROMPT = """You are an advanced AI Agent with high discretion, mimicking the rigor of systems like OpenEvidence.
You operate on a strict Reason-Act-Observe-Answer cycle (ReAct).

Core Principles:
1. HIGH DISCRETION: Do not guess or hallucinate facts. You must rely solely on the evidence provided by your Memory (VectorRAG and GraphRAG) or by external Tools (e.g. web search).
2. CITATION: If you make a claim, cite the source or tool observation. If there is no evidence to support a claim, explicitly state that it is unknown.
3. LOGICAL PROGRESSION: If a search observation doesn't have the answer, search again with different terms or consult a different tool.

You have access to a memory system that auto-retrieves context based on the user's query, and you have access to a set of MCP (Model Context Protocol) tools.

FORMAT INSTRUCTIONS:
Always respond in one of two formats.

To execute a tool or search memory again:
Thought: Detail your reasoning for the next step. What do I need to find out?
Action:
```json
{
  "server": "server_name",
  "tool": "tool_name",
  "arguments": { "arg1": "value" }
}
```

To provide the final answer to the user:
Thought: I have sufficient evidence to answer the user's question, or I've hit a dead end and must admit I don't know.
Answer: <Your final detailed answer with citations in brackets [source]>
"""

class ReActAgent:
    def __init__(self, memory_manager: MemoryManager, mcp_client: MCPClientManager, model_name: str = "gemini/gemini-2.5-pro"):
        self.memory = memory_manager
        self.mcp = mcp_client
        self.model_name = model_name
        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
    async def process_user_query(self, query: str, max_iterations: int = 5) -> str:
        # First, query our internal long-term memory
        memory_context = self.memory.query_memory(query)
        
        # Save user query to memory for future context
        self.memory.add_memory(query, source="user_input")
        
        # fetch available tools
        tools = await self.mcp.get_all_tools()
        tools_desc = "\nAvailable Tools:\n"
        for t in tools:
            tools_desc += f"- Server: {t['server']}, Tool: {t['name']}, Desc: {t['description']}, Schema: {json.dumps(t['inputSchema'])}\n"
        if not tools:
            tools_desc = "\nNo external tools available at the moment.\n"

        prompt = f"""User Query: {query}

Current Semantic and Relational Memory Context for this query:
{memory_context}

{tools_desc}
"""
        self.chat_history.append({"role": "user", "content": prompt})
        
        for i in range(max_iterations):
            try:
                response = await acompletion(
                    model=self.model_name,
                    messages=self.chat_history
                )
                content = response.choices[0].message.content
                self.chat_history.append({"role": "assistant", "content": content})
                print(f"\n[Agent Thought/Action]:\n{content}")
                
                # Check if it's an action or final answer
                if "Answer:" in content:
                    answer_text = content.split("Answer:", 1)[1].strip()
                    # Store the final answer in memory
                    self.memory.add_memory(answer_text, source="agent_thought_process")
                    return answer_text
                    
                if "Action:" in content:
                    # parse JSON block
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        action_dict = json.loads(json_match.group(1))
                        server = action_dict.get("server")
                        tool = action_dict.get("tool")
                        args = action_dict.get("arguments", {})
                        
                        print(f"[Executing Tool] {server}.{tool}({args})")
                        obs = await self.mcp.call_tool(server, tool, args)
                        
                        # Add observation
                        obs_text = f"Observation:\n{obs}"
                        self.chat_history.append({"role": "user", "content": obs_text})
                        print(f"[{server}.{tool} response]: {str(obs)[:200]}...")
                    else:
                        error_msg = "Observation: Format Error: Could not parse json Action block. Remember to use ```json ... ``` format for Action."
                        self.chat_history.append({"role": "user", "content": error_msg})
                else:
                    error_msg = "Observation: Format Error: No 'Action:' or 'Answer:' found. You must output one or the other."
                    self.chat_history.append({"role": "user", "content": error_msg})
                     
            except Exception as e:
                print(f"Error during ReAct step: {e}")
                self.chat_history.append({"role": "user", "content": f"Observation: System Error calling LLM: {str(e)}"})
                
        return "Agent reached maximum iterations without finding a final answer."
