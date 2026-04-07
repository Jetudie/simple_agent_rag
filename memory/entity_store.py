import os
import json
import numpy as np
from typing import Dict, Any, Optional
from fastembed import TextEmbedding

class EntityStore:
    def __init__(self, path: str = "entity_db.json"):
        self.path = path
        self.db: Dict[str, Dict[str, Any]] = {}
        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self.embeddings: Dict[str, np.ndarray] = {}
        self.load()
        self._rebuild_embeddings()
        
    def _rebuild_embeddings(self):
        keys = list(self.db.keys())
        if keys:
            embs = list(self.embedding_model.embed(keys))
            for k, e in zip(keys, embs):
                self.embeddings[k] = e
        
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
        
        # update vec
        emb = list(self.embedding_model.embed([name_key]))[0]
        self.embeddings[name_key] = emb
        
        return f"Successfully {action} entity '{name}'."
        
    def get_entity(self, name: str, threshold: float = 0.75) -> Optional[Dict[str, Any]]:
        name_key = name.strip().lower()
        if name_key in self.db:
            return {"name": name_key, **self.db[name_key]}
        
        # Fallback substring search
        for key, val in self.db.items():
            if name_key in key or key in name_key:
                return {"name": key, **val}
                
        # Semantic Vector fuzzy search
        if not self.embeddings:
            return None
            
        query_emb = list(self.embedding_model.embed([name_key]))[0]
        best_key = ""
        best_score = -1.0
        
        for key, emb in self.embeddings.items():
            score = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb))
            if score > best_score:
                best_score = score
                best_key = key
                
        if best_score >= threshold:
            return {"name": best_key, **self.db[best_key]}
                
        return None
        
    def delete_entity(self, name: str) -> str:
        name_key = name.strip().lower()
        
        # Determine actual key using the same search logic
        target_key = name_key
        if target_key not in self.db:
            ent = self.get_entity(name_key)
            if ent:
                target_key = ent["name"]
                
        if target_key in self.db:
            del self.db[target_key]
            if target_key in self.embeddings:
                del self.embeddings[target_key]
            self.save()
            return f"Successfully deleted entity '{target_key}'."
            
        return f"Entity '{name}' not found."
