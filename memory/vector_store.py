import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

class VectorStore:
    def __init__(self, path: str = "qdrant_db", collection_name: str = "agent_memory"):
        self.client = QdrantClient(path=path)
        self.collection_name = collection_name
        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        # Ensure collection exists
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            # fastembed bge-small-en-v1.5 output dim is 384
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            
    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None):
        """Add texts to the vector store."""
        if not texts:
            return
            
        if metadatas is None:
            metadatas = [{} for _ in texts]
            
        embeddings = list(self.embedding_model.embed(texts))
        
        points = []
        for text, metadata, emb in zip(texts, metadatas, embeddings):
            point_id = str(uuid.uuid4())
            payload = {"text": text, **metadata}
            points.append(PointStruct(id=point_id, vector=emb.tolist(), payload=payload))
            
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for most similar texts."""
        query_vector = list(self.embedding_model.embed([query]))[0]
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector.tolist(),
            limit=limit
        )
        
        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"}
            }
            for hit in results
        ]
