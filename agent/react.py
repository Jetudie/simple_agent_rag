import json
import re
import os
from typing import List, Dict, Any, Optional
from litellm import acompletion
from tools.mcp_client import MCPClientManager

class ReActAgent:
    def __init__(self, mcp_client: MCPClientManager, model_name: str = "ollama/gemma4:e4b", api_base: str = "http://localhost:11434"):
        self.mcp = mcp_client
        self.model_name = model_name
        self.api_base = api_base
        
        # Load system prompt from skills.md
        self.system_prompt = "You are an advanced AI Agent."
        skills_path = "skills.md"
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
                
        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        
    async def process_user_query(self, query: str, max_iterations: int = 8) -> str:
        await self.mcp.call_tool("internal", "log_diary_step", {"role": "USER", "content": query})
        
        memory_context = await self.mcp.call_tool("internal", "get_memory_context", {"query": query})
        await self.mcp.call_tool("internal", "add_user_memory", {"text": query})
        
        tools = await self.mcp.get_all_tools()
        tools_desc = "\nAvailable MCP Tools:\n"
        for t in tools:
            tools_desc += f"- Server: {t['server']}, Tool: {t['name']}, Desc: {t['description']}, Schema: {json.dumps(t['inputSchema'])}\n"

        prompt = f"User Query: {query}\n\nCurrent Semantic and Relational Memory Context:\n{memory_context}\n{tools_desc}"
        self.chat_history.append({"role": "user", "content": prompt})
        
        for i in range(max_iterations):
            try:
                response = await acompletion(
                    model=self.model_name,
                    api_base=self.api_base,
                    messages=self.chat_history
                )
                content = response.choices[0].message.content
                self.chat_history.append({"role": "assistant", "content": content})
                print(f"\n[Agent Thought/Action]:\n{content}")
                await self.mcp.call_tool("internal", "log_diary_step", {"role": "AGENT_STEP", "content": content})
                
                # Programmatic Harness - Enforce Checklist
                if "Checklist:" not in content:
                    error_msg = "Observation: Formatting Harness Violation: Mandatory 'Checklist:' block was missing from your output. Please retry your thought process including the checklist state."
                    self.chat_history.append({"role": "user", "content": error_msg})
                    await self.mcp.call_tool("internal", "log_diary_step", {"role": "HARNESS_VIOLATION", "content": error_msg})
                    print(f"[Harness Violation Detected]")
                    continue
                
                if "Answer:" in content:
                    answer_text = content.split("Answer:", 1)[1].strip()
                    await self.mcp.call_tool("internal", "add_agent_memory", {"text": answer_text})
                    await self.mcp.call_tool("internal", "log_diary_step", {"role": "AGENT_FINAL_ANSWER", "content": answer_text})
                    return answer_text
                    
                if "Action:" in content:
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        action_dict = json.loads(json_match.group(1))
                        server = action_dict.get("server")
                        tool = action_dict.get("tool")
                        args = action_dict.get("arguments", {})
                        
                        print(f"[Executing Tool] {server}.{tool}({args})")
                        obs = await self.mcp.call_tool(server, tool, args)
                        
                        obs_text = f"Observation:\n{obs}"
                        self.chat_history.append({"role": "user", "content": obs_text})
                        await self.mcp.call_tool("internal", "log_diary_step", {"role": "OBSERVATION", "content": str(obs)})
                        print(f"[{server}.{tool} response]: {str(obs)[:200]}...")
                    else:
                        error_msg = "Observation: Format Error: Could not parse json Action block. Remember to use ```json ... ``` format for Action."
                        self.chat_history.append({"role": "user", "content": error_msg})
                        await self.mcp.call_tool("internal", "log_diary_step", {"role": "ERROR", "content": error_msg})
                else:
                    error_msg = "Observation: Format Error: No 'Action:' or 'Answer:' found. You must output one or the other."
                    self.chat_history.append({"role": "user", "content": error_msg})
                    await self.mcp.call_tool("internal", "log_diary_step", {"role": "ERROR", "content": error_msg})
                     
            except Exception as e:
                err = f"System Error calling LLM: {str(e)}"
                print(f"Error during ReAct step: {e}")
                self.chat_history.append({"role": "user", "content": f"Observation: {err}"})
                await self.mcp.call_tool("internal", "log_diary_step", {"role": "ERROR", "content": err})
                if "Connection" in str(e) or "connect" in str(e).lower() or "WinError 10061" in str(e):
                     return f"Failed to connect to local Ollama at {self.api_base}. Ensure Ollama is running.\nError: {e}"
                
        err = "Agent reached maximum iterations without finding a final answer."
        try:
            await self.mcp.call_tool("internal", "log_diary_step", {"role": "AGENT_FINAL_ANSWER", "content": err})
        except: pass
        return err
