import networkx as nx
import json
import os
import numpy as np
from typing import List, Tuple
from fastembed import TextEmbedding

class GraphStore:
    def __init__(self, path: str = "graph_db.json"):
        self.path = path
        self.graph = nx.DiGraph()
        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        # In-memory dictionary for quick vector distances: entity_str -> np.ndarray
        self.embeddings: dict[str, np.ndarray] = {}
        self.load()
        self._rebuild_embeddings()
        
    def _rebuild_embeddings(self):
        nodes = list(self.graph.nodes)
        if not nodes:
            return
            
        nodes_to_embed = [n for n in nodes if n not in self.embeddings]
        if nodes_to_embed:
            embs = list(self.embedding_model.embed(nodes_to_embed))
            for n, e in zip(nodes_to_embed, embs):
                self.embeddings[n] = e
        
    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
            except Exception as e:
                print(f"Error loading graph: {e}")
                self.graph = nx.DiGraph()
                
    def save(self):
        data = nx.node_link_data(self.graph)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
    def add_triplets(self, triplets: List[Tuple[str, str, str]]):
        """Add (subject, predicate, object) triplets to the graph."""
        changed = False
        new_nodes = set()
        for subj, pred, obj in triplets:
            if not subj or not pred or not obj:
                continue
            subj, pred, obj = subj.strip().lower(), pred.strip().lower(), obj.strip().lower()
            if not self.graph.has_node(subj):
                self.graph.add_node(subj)
                new_nodes.add(subj)
            if not self.graph.has_node(obj):
                self.graph.add_node(obj)
                new_nodes.add(obj)
            self.graph.add_edge(subj, obj, relation=pred)
            changed = True
            
        if changed:
            self.save()
            
        # Update embeddings for new nodes
        if new_nodes:
            embs = list(self.embedding_model.embed(list(new_nodes)))
            for n, e in zip(list(new_nodes), embs):
                self.embeddings[n] = e
                
    def delete_node(self, entity: str) -> bool:
        """Deletes a node and all its edges from the graph."""
        entity = entity.strip().lower()
        closest = self._find_closest_node(entity, threshold=0.85)
        if closest:
            self.graph.remove_node(closest)
            if closest in self.embeddings:
                del self.embeddings[closest]
            self.save()
            return True
        return False

    def _find_closest_node(self, entity: str, threshold: float = 0.75) -> str:
        """Finds closest node in graph string-wise or vector-wise."""
        entity = entity.strip().lower()
        if self.graph.has_node(entity):
            return entity
            
        if not self.embeddings: # graph is empty
            return ""
            
        # Vector similarity search using fastembed
        query_emb = list(self.embedding_model.embed([entity]))[0]
        
        best_node = ""
        best_score = -1.0
        
        for node, emb in self.embeddings.items():
            # Cosine similarity
            score = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb))
            if score > best_score:
                best_score = score
                best_node = node
                
        if best_score >= threshold:
            return best_node
            
        return ""
        
    def get_related_triplets(self, entity: str, max_depth: int = 2) -> List[str]:
        """Get context around an entity using BFS."""
        starting_node = self._find_closest_node(entity, threshold=0.7)
        
        if not starting_node:
            return []
            
        triplets = []
        visited_nodes = {starting_node}
        queue = [(starting_node, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
                
            # Outgoing edges
            for neighbor in self.graph.successors(current):
                edge_data = self.graph.get_edge_data(current, neighbor)
                relation = edge_data.get('relation', 'related_to')
                triplets.append(f"({current}, {relation}, {neighbor})")
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, depth + 1))
                    
            # Incoming edges
            for neighbor in self.graph.predecessors(current):
                edge_data = self.graph.get_edge_data(neighbor, current)
                relation = edge_data.get('relation', 'related_to')
                triplets.append(f"({neighbor}, {relation}, {current})")
                if neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, depth + 1))
                    
        return list(set(triplets))
