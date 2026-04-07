import os
import json
from typing import Dict, Any, Optional

class EntityStore:
    def __init__(self, path: str = "entity_db.json"):
        self.path = path
        self.db: Dict[str, Dict[str, Any]] = {}
        self.load()
        
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
            except Exception as e:
                print(f"Error loading entity db: {e}")
                self.db = {}
                
    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, indent=2)
            
    def upsert_entity(self, name: str, entity_type: str, attributes: Dict[str, Any]) -> str:
        name_key = name.strip().lower()
        if not name_key:
            return "Error: Entity name cannot be empty."
            
        # Merge if exists, else create new
        if name_key in self.db:
            existing = self.db[name_key].get("attributes", {})
            existing.update(attributes)
            self.db[name_key]["attributes"] = existing
            self.db[name_key]["type"] = entity_type
            action = "Updated"
        else:
            self.db[name_key] = {
                "type": entity_type,
                "attributes": attributes
            }
            action = "Created"
            
        self.save()
        return f"Successfully {action} entity '{name}'."
        
    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        name_key = name.strip().lower()
        if name_key in self.db:
            return {"name": name, **self.db[name_key]}
        
        # Fallback pseudo-search
        for key, val in self.db.items():
            if name_key in key or key in name_key:
                return {"name": key, **val}
                
        return None
        
    def delete_entity(self, name: str) -> str:
        name_key = name.strip().lower()
        if name_key in self.db:
            del self.db[name_key]
            self.save()
            return f"Successfully deleted entity '{name}'."
        return f"Entity '{name}' not found."
