from mcp.server.fastmcp import FastMCP
from memory.manager import MemoryManager
from memory.diary import Diary

mcp = FastMCP("InternalAgentMemory")
memory = MemoryManager(model_name="ollama/gemma4:e4b", api_base="http://localhost:11434")
diary = Diary()

@mcp.tool()
def get_memory_context(query: str) -> str:
    """Get the semantic, relational, and entity context for a query."""
    return memory.query_memory(query)

@mcp.tool()
def add_user_memory(text: str) -> str:
    """Add a raw observation to the memory engine."""
    memory.add_memory(text, source="user_input")
    return "Stored in memory."

@mcp.tool()
def add_agent_memory(text: str) -> str:
    """Add the agent's finalized answer to memory."""
    memory.add_memory(text, source="agent_thought_process")
    return "Stored agent answer in memory."

@mcp.tool()
def log_diary_step(role: str, content: str) -> str:
    """Log an interaction directly to the markdown diary."""
    diary.log(role, content)
    return "Logged to diary."

@mcp.tool()
def read_diary(date: str) -> str:
    """Reads full thought process of a past day (YYYY-MM-DD)."""
    return diary.read_diary(date)

@mcp.tool()
def list_diaries() -> str:
    """Lists all available diary dates."""
    return ", ".join(diary.list_diaries())

@mcp.tool()
def delete_graph_node(entity: str) -> str:
    """Deletes an entity node from the knowledge graph."""
    deleted = memory.graph_store.delete_node(entity)
    return f"Deleted node '{entity}'? {deleted}"

@mcp.tool()
def upsert_entity(name: str, type: str, attributes: dict) -> str:
    """Create or update structured JSON profile for person/product/topic."""
    return memory.entity_store.upsert_entity(name, type, attributes)

@mcp.tool()
def get_entity(name: str) -> str:
    """Force grab a profile from entity DB."""
    import json
    ent = memory.entity_store.get_entity(name)
    return json.dumps(ent) if ent else f"Entity '{name}' not found."

@mcp.tool()
def delete_entity(name: str) -> str:
    """Delete profile from entity DB."""
    return memory.entity_store.delete_entity(name)

@mcp.tool()
def validate_source(source: str) -> str:
    """Strict verification if a source path/domain is whitelisted."""
    source_lower = source.lower()
    whitelist = ["internal_memory", "entity_store", "diary", "local_documents", "verified_user", "localhost"]
    if any(w in source_lower for w in whitelist):
        return f"Source '{source}' is WHITELISTED and trusted."
    else:
        return f"Source '{source}' is NOT whitelisted. Do not trust this information blindly."

if __name__ == "__main__":
    mcp.run()
