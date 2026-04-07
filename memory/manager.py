import json
from typing import List, Dict, Any, Tuple
from memory.vector_store import VectorStore
from memory.graph_store import GraphStore
from memory.entity_store import EntityStore
from litellm import completion

class MemoryManager:
    def __init__(self, model_name: str = "ollama/qwen3:4b", api_base: str = "http://localhost:11434"):
        """Initialize both memory stores."""
        self.vector_store = VectorStore()
        self.graph_store = GraphStore()
        self.entity_store = EntityStore()
        self.model_name = model_name
        self.api_base = api_base
        
    def add_memory(self, text: str, source: str = "user"):
        """Process incoming text, adding it to both Vector and Graph stores."""
        # 1. Add raw chunks to Vector RAG
        self.vector_store.add_texts([text], [{"source": source}])
        
        # 2. Extract triplets for GraphRAG
        triplets = self._extract_triplets(text)
        if triplets:
            self.graph_store.add_triplets(triplets)
            
    def query_memory(self, query: str) -> str:
        """Search both memories and synthesize the results."""
        # Query Vector RAG
        vector_results = self.vector_store.search(query, limit=3)
        vector_context = "\n".join([f"- {r['text']} (source: {r['metadata'].get('source', 'unknown')})" for r in vector_results])
        
        # Query GraphRAG & EntityStore using LLM to extract entities from query
        entities = self._extract_entities_from_query(query)
        graph_context_list = []
        entity_profiles = []
        for entity in entities:
            graph_context_list.extend(self.graph_store.get_related_triplets(entity))
            profile = self.entity_store.get_entity(entity)
            if profile:
                entity_profiles.append(json.dumps(profile))
                
        graph_context_list = list(set(graph_context_list))
        graph_context = "\n".join([f"- {g}" for g in graph_context_list])
        entity_context = "\n".join(entity_profiles)
        
        context = "### Semantic Memory Context ###\n"
        context += vector_context if vector_context else "No semantic memory found."
        context += "\n\n### Graph/Relational Memory Context ###\n"
        context += graph_context if graph_context else "No relational memory found."
        context += "\n\n### Structured Entity Profiles ###\n"
        context += entity_context if entity_context else "No structured entities found."
        
        return context

    def _extract_triplets(self, text: str) -> List[Tuple[str, str, str]]:
        """Use LLM to extract (subject, predicate, object) triplets."""
        prompt = f"""
        Extract key knowledge triplets from the following text. 
        Format as a strict JSON list of lists: [["subject1", "predicate1", "object1"], ...].
        Only output the JSON list, no markdown or explanation.
        Text: {text}
        """
        try:
            response = completion(
                model=self.model_name,
                api_base=self.api_base,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            # Remove potential markdown block chars
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            triplets = json.loads(content)
            return triplets
        except Exception as e:
            print(f"Failed to extract triplets: {e}")
            return []
            
    def _extract_entities_from_query(self, query: str) -> List[str]:
        """Extract key entities from a query to search the graph store."""
        prompt = f"""
        Extract the most important entities (people, places, concepts) from this query to search a knowledge graph.
        Return a strict JSON list of strings: ["entity1", "entity2"].
        Only output the JSON list, no markdown or explanation.
        Query: {query}
        """
        try:
            response = completion(
                model=self.model_name,
                api_base=self.api_base,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            entities = json.loads(content)
            return entities
        except Exception as e:
            print(f"Failed to extract entities from query: {e}")
            return []
