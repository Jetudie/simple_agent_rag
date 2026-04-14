from mcp.server.fastmcp import FastMCP
from memory.manager import MemoryManager
from memory.diary import Diary

mcp = FastMCP("InternalAgentMemory")
import os
model_name = os.getenv("OPENAI_MODEL_NAME", "ollama/gemma4:e4b")
api_base = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
api_key = os.getenv("OPENAI_API_KEY", "ollama")
agent_learning_enabled = os.getenv("AGENT_LEARNING_ENABLED", "False").lower() == "true"
workspace_read_access = os.getenv("WORKSPACE_READ_ACCESS", "False").lower() == "true"
memory = MemoryManager(model_name=model_name, api_base=api_base, api_key=api_key)
diary = Diary()

@mcp.tool()
def get_memory_context(query: str) -> str:
    """Get the semantic, relational, and entity context for a query."""
    return memory.query_memory(query)



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
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
    deleted = memory.graph_store.delete_node(entity)
    return f"Deleted node '{entity}'? {deleted}"

@mcp.tool()
def upsert_entity(name: str, type: str, attributes: dict) -> str:
    """Create or update structured JSON profile for person/product/topic."""
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
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
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
    return memory.entity_store.delete_entity(name)

@mcp.tool()
def memorize_fact(fact: str) -> str:
    """Actively inject a new fact directly into the Vector and Graph databases."""
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
    memory.add_memory(fact, source="agent_active_learning")
    return f"Successfully ingrained fact into subconscious memory."

@mcp.tool()
def add_graph_edge(subject: str, predicate: str, object_node: str) -> str:
    """Surgically explicitly map a conceptual relationship in the Graph Database without background extraction."""
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
    memory.graph_store.add_triplets([(subject, predicate, object_node)])
    return f"Created Graph edge: ({subject}) -[{predicate}]-> ({object_node})"

@mcp.tool()
def list_notes() -> str:
    """Returns a list of all self-authored learning notes the agent has created."""
    import os
    if not os.path.exists("notes"):
        return "Notes folder is empty."
    return ", ".join([f for f in os.listdir("notes") if f.endswith(".md")])

@mcp.tool()
def read_note(filename: str) -> str:
    """Read full content of a specific note."""
    import os
    path = os.path.join("notes", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"Note {filename} not found."

@mcp.tool()
def write_note(filename: str, content: str) -> str:
    """Create or overwrite a self-learning notebook markdown file."""
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
    import os
    if not os.path.exists("notes"):
        os.makedirs("notes")
    path = os.path.join("notes", filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Successfully wrote to {filename}."

@mcp.tool()
def append_note(filename: str, content: str) -> str:
    """Append text to an existing note."""
    if not agent_learning_enabled:
        return "System Error: Agent Learning Mode is currently DISABLED."
    import os
    if not os.path.exists("notes"):
        os.makedirs("notes")
    path = os.path.join("notes", filename)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + content)
    return f"Successfully appended to {filename}."

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """Lists files in a given directory safely. Looks for AGENT.md automatically."""
    import os
    
    if not workspace_read_access:
        # Sandboxed mode: only let it see safe folders or the project root.
        if path not in [".", "documents", "notes", "diary"]:
            return f"System Error: WORKSPACE_READ_ACCESS is disabled. You are sandboxed to reading only '.' or 'documents/', 'notes/', and 'diary/'."
            
    base_dir = os.path.abspath(path)
    # Simple check to prevent escaping the project root
    if not base_dir.startswith(os.getcwd()):
         return "System Error: Path traversal attempt blocked."
         
    if not os.path.exists(base_dir):
        return f"Directory {path} not found."
        
    items = []
    has_agent_md = False
    for filename in os.listdir(base_dir):
        if filename == "AGENT.md":
            has_agent_md = True
        mapped = f"[DIR]  {filename}/" if os.path.isdir(os.path.join(base_dir, filename)) else f"[FILE] {filename}"
        items.append(mapped)
        
    res = "\n".join(items)
    if has_agent_md:
        res = "🚨 [CRITICAL NOTE]: An 'AGENT.md' architectural file exists here! You should read it immediately for context!\n\n" + res
    return res

@mcp.tool()
def read_source_file(path: str) -> str:
    """Reads the raw text of a file."""
    import os
    
    if not workspace_read_access:
        if not (path.startswith("documents/") or path.startswith("notes/") or path.startswith("diary/") or path in ["AGENT.md", "walkthrough.md"]):
            return "System Error: WORKSPACE_READ_ACCESS is disabled. Sandboxed from reading deep source files."

    base_path = os.path.abspath(path)
    if not base_path.startswith(os.getcwd()):
        return "System Error: Path traversal attempt blocked."
        
    if not os.path.isfile(base_path):
        return f"File {path} not found."
        
    try:
        with open(base_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
         return f"Error reading file: {str(e)}"

@mcp.tool()
def validate_source(source: str) -> str:
    """Strict verification if a source path/domain is whitelisted."""
    source_lower = source.lower()
    whitelist = ["internal_memory", "entity_store", "diary", "local_documents", "verified_user", "localhost"]
    if any(w in source_lower for w in whitelist):
        return f"Source '{source}' is WHITELISTED and trusted."
    else:
        return f"Source '{source}' is NOT whitelisted. Do not trust this information blindly."

# Trigger the document sync so trusted vectors are loaded before any query arrives
memory.sync_local_documents()
memory.sync_agent_notes()

if __name__ == "__main__":
    mcp.run()
