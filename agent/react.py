import json
import re
import os
from typing import List, Dict, Any, Optional
from litellm import acompletion
from memory.manager import MemoryManager
from tools.mcp_client import MCPClientManager
from memory.diary import Diary

class ReActAgent:
    def __init__(self, memory_manager: MemoryManager, mcp_client: MCPClientManager, model_name: str = "ollama/qwen3:4b", api_base: str = "http://localhost:11434"):
        self.memory = memory_manager
        self.mcp = mcp_client
        self.diary = Diary()
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
        self.diary.log("USER", query)
        
        memory_context = self.memory.query_memory(query)
        self.memory.add_memory(query, source="user_input")
        
        tools = await self.mcp.get_all_tools()
        tools_desc = "\nAvailable MCP Tools:\n"
        for t in tools:
            tools_desc += f"- Server: {t['server']}, Tool: {t['name']}, Desc: {t['description']}, Schema: {json.dumps(t['inputSchema'])}\n"
        
        tools_desc += "\nAvailable Internal Tools (server: \"internal\"):\n"
        tools_desc += "- Tool: read_diary, Desc: Reads full thought process of a past day, Schema: {\"date\": \"YYYY-MM-DD\"}\n"
        tools_desc += "- Tool: list_diaries, Desc: Lists all available diary dates, Schema: {}\n"
        tools_desc += "- Tool: delete_graph_node, Desc: Deletes an entity node from the knowledge graph, Schema: {\"entity\": \"entity_name\"}\n"
        tools_desc += "- Tool: upsert_entity, Desc: Create or update structured JSON profile for person/product/topic, Schema: {\"name\": \"string\", \"type\": \"string\", \"attributes\": {\"key\": \"value\"}}\n"
        tools_desc += "- Tool: get_entity, Desc: Force grab a profile from entity DB, Schema: {\"name\": \"string\"}\n"
        tools_desc += "- Tool: delete_entity, Desc: Delete profile from entity DB, Schema: {\"name\": \"string\"}\n"

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
                self.diary.log("AGENT_STEP", content)
                
                if "Answer:" in content:
                    answer_text = content.split("Answer:", 1)[1].strip()
                    self.memory.add_memory(answer_text, source="agent_thought_process")
                    self.diary.log("AGENT_FINAL_ANSWER", answer_text)
                    return answer_text
                    
                if "Action:" in content:
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        action_dict = json.loads(json_match.group(1))
                        server = action_dict.get("server")
                        tool = action_dict.get("tool")
                        args = action_dict.get("arguments", {})
                        
                        print(f"[Executing Tool] {server}.{tool}({args})")
                        obs = ""
                        
                        if server == "internal":
                            if tool == "read_diary":
                                obs = self.diary.read_diary(args.get("date", ""))
                            elif tool == "list_diaries":
                                obs = ", ".join(self.diary.list_diaries())
                            elif tool == "delete_graph_node":
                                deleted = self.memory.graph_store.delete_node(args.get("entity", ""))
                                obs = f"Deleted node '{args.get('entity')}'? {deleted}"
                            elif tool == "upsert_entity":
                                obs = self.memory.entity_store.upsert_entity(args.get("name", ""), args.get("type", "Topic"), args.get("attributes", {}))
                            elif tool == "get_entity":
                                ent = self.memory.entity_store.get_entity(args.get("name", ""))
                                obs = json.dumps(ent) if ent else f"Entity '{args.get('name')}' not found."
                            elif tool == "delete_entity":
                                obs = self.memory.entity_store.delete_entity(args.get("name", ""))
                            else:
                                obs = f"Unknown internal tool {tool}"
                        else:
                            obs = await self.mcp.call_tool(server, tool, args)
                        
                        obs_text = f"Observation:\n{obs}"
                        self.chat_history.append({"role": "user", "content": obs_text})
                        self.diary.log("OBSERVATION", str(obs))
                        print(f"[{server}.{tool} response]: {str(obs)[:200]}...")
                    else:
                        error_msg = "Observation: Format Error: Could not parse json Action block. Remember to use ```json ... ``` format for Action."
                        self.chat_history.append({"role": "user", "content": error_msg})
                        self.diary.log("ERROR", error_msg)
                else:
                    error_msg = "Observation: Format Error: No 'Action:' or 'Answer:' found. You must output one or the other."
                    self.chat_history.append({"role": "user", "content": error_msg})
                    self.diary.log("ERROR", error_msg)
                     
            except Exception as e:
                err = f"System Error calling LLM: {str(e)}"
                print(f"Error during ReAct step: {e}")
                self.chat_history.append({"role": "user", "content": f"Observation: {err}"})
                self.diary.log("ERROR", err)
                if "Connection" in str(e) or "connect" in str(e).lower() or "WinError 10061" in str(e):
                     return f"Failed to connect to local Ollama at {self.api_base}. Ensure Ollama is running.\nError: {e}"
                
        err = "Agent reached maximum iterations without finding a final answer."
        self.diary.log("AGENT_FINAL_ANSWER", err)
        return err
