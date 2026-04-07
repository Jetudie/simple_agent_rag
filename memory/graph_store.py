import networkx as nx
import json
import os
from typing import List, Dict, Any, Tuple

class GraphStore:
    def __init__(self, path: str = "graph_db.json"):
        self.path = path
        self.graph = nx.DiGraph()
        self.load()
        
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
        for subj, pred, obj in triplets:
            if not subj or not pred or not obj:
                continue
            subj, pred, obj = subj.strip().lower(), pred.strip().lower(), obj.strip().lower()
            if not self.graph.has_node(subj):
                self.graph.add_node(subj)
            if not self.graph.has_node(obj):
                self.graph.add_node(obj)
            self.graph.add_edge(subj, obj, relation=pred)
            changed = True
        if changed:
            self.save()
        
    def get_related_triplets(self, entity: str, max_depth: int = 2) -> List[str]:
        """Get context around an entity using BFS."""
        entity = entity.strip().lower()
        if not self.graph.has_node(entity):
            # Try partial match if exact doesn't exist
            matches = [n for n in self.graph.nodes if entity in str(n) or str(n) in entity]
            if not matches:
                return []
            entity = matches[0]
            
        triplets = []
        visited_nodes = {entity}
        queue = [(entity, 0)]
        
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
