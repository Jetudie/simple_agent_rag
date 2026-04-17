from mcp.server.fastmcp import FastMCP
from memory.manager import MemoryManager
from memory.diary import Diary

mcp = FastMCP("InternalAgentMemory")
import os
model_name = os.getenv("OPENAI_MODEL_NAME", "gemma4:e2b")
api_base = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
api_key = os.getenv("OPENAI_API_KEY", "ollama")
agent_learning_enabled = os.getenv("AGENT_LEARNING_ENABLED", "False").lower() == "true"
workspace_read_access = os.getenv("WORKSPACE_READ_ACCESS", "False").lower() == "true"

allow_terminal_execution = os.getenv("ALLOW_TERMINAL_EXECUTION", "False").lower() == "true"
raw_write_dirs = os.getenv("WORKSPACE_ALLOWED_WRITE_DIRS", "sandbox,notes,documents")
workspace_allowed_write_dirs = [d.strip() for d in raw_write_dirs.split(",") if d.strip()]
virtual_cwd = os.getcwd()

memory = MemoryManager(model_name=model_name, api_base=api_base, api_key=api_key)
diary = Diary()

# Create sandbox directory if it doesn't exist
os.makedirs("sandbox", exist_ok=True)

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

# --- SWE Agent Tools ---

def _is_path_write_approved(path: str) -> bool:
    import os
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(os.getcwd()):
        return False
    # Check if the folder is inside any of the allowed dirs
    for d in workspace_allowed_write_dirs:
        allowed_base = os.path.abspath(d)
        if abs_path.startswith(allowed_base):
            return True
    return False

@mcp.tool()
def write_new_file(path: str, content: str) -> str:
    """Creates a new file from scratch. Fails if file exists or path is outside allowed write dirs."""
    import os
    if not _is_path_write_approved(path):
        return f"System Error: Path '{path}' is not inside allowed write directories ({workspace_allowed_write_dirs})."
        
    if os.path.exists(path):
        return f"System Error: File '{path}' already exists! Use patch_file to edit it."
        
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Successfully created '{path}'."

@mcp.tool()
def patch_file(path: str, search_string: str, replace_string: str) -> str:
    """Replaces a specific block of text in a file. Very safe."""
    import os
    if not _is_path_write_approved(path):
        return f"System Error: Path '{path}' is not inside allowed write directories ({workspace_allowed_write_dirs})."
        
    if not os.path.exists(path):
        return f"System Error: File '{path}' does not exist!"
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if search_string not in content:
        return "System Error: The search_string was not found exactly in the file. No changes made."
        
    new_content = content.replace(search_string, replace_string, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    return f"Successfully patched '{path}'."

@mcp.tool()
def grep_codebase(regex_pattern: str, dir: str = ".") -> str:
    """Searches .py, .md, and .json files for a specific regex pattern."""
    import os
    import re
    if not workspace_read_access:
        if dir not in [".", "documents", "notes", "diary", "sandbox"]:
            return "System Error: WORKSPACE_READ_ACCESS is disabled."
            
    base_dir = os.path.abspath(dir)
    if not base_dir.startswith(os.getcwd()):
         return "System Error: Path traversal attempt blocked."
         
    matches = []
    try:
        pattern = re.compile(regex_pattern)
        for root, dirs, files in os.walk(base_dir):
            if ".git" in root or "__pycache__" in root or ".venv" in root:
                continue
            for file in files:
                if file.endswith((".py", ".md", ".json")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines):
                                if pattern.search(line):
                                    rel_path = os.path.relpath(file_path, os.getcwd())
                                    matches.append(f"{rel_path}:{i+1}: {line.strip()}")
                    except Exception:
                        pass
        return "\n".join(matches) if matches else "No matches found."
    except Exception as e:
        return f"Regex Error: {e}"

@mcp.tool()
def run_command(command: str) -> str:
    """Stateful terminal execution. Keeps track of CWD via cd command interception."""
    global virtual_cwd
    import os
    import subprocess
    
    if not allow_terminal_execution:
        return "System Error: Terminal execution is currently DISABLED (ALLOW_TERMINAL_EXECUTION=False)."
        
    cmd_parts = command.strip().split(" ")
    if cmd_parts[0] == "cd" and len(cmd_parts) > 1:
        target_dir = " ".join(cmd_parts[1:])
        new_dir = os.path.abspath(os.path.join(virtual_cwd, target_dir))
        if os.path.exists(new_dir) and os.path.isdir(new_dir):
            virtual_cwd = new_dir
            return f"Changed directory to: {virtual_cwd}"
        else:
            return f"Error: Directory '{target_dir}' does not exist."
            
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=virtual_cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        out_str = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            out_str += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            out_str += f"STDERR:\n{result.stderr}\n"
        return out_str
    except subprocess.TimeoutExpired:
        return "System Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"System Error executing command: {str(e)}"

# Trigger the document sync so trusted vectors are loaded before any query arrives
memory.sync_local_documents()
memory.sync_agent_notes()

if __name__ == "__main__":
    mcp.run()
