import random
import re
from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.docstore.document import Document
import os
import requests
from langchain.embeddings.base import Embeddings

class OllamaLocalEmbeddings(Embeddings):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.replace("/v1", "").rstrip("/")
        self.model = model

    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": self.model,
            "prompt": text
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            try:
                url_new = f"{self.base_url}/api/embed"
                payload_new = {
                    "model": self.model,
                    "input": text
                }
                response = requests.post(url_new, json=payload_new)
                response.raise_for_status()
                return response.json()["embeddings"][0]
            except Exception as e2:
                raise RuntimeError(f"Ollama embedding failed: {e} | {e2}")

class DrivingMemory:
    def __init__(self, env) -> None:
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        if embedding_provider == "ollama":
            base_url = os.getenv("EMBEDDING_API_BASE", "http://127.0.0.1:11434/v1")
            model_name = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
            self.embedding = OllamaLocalEmbeddings(base_url=base_url, model=model_name)
        else:
            self.embedding = OpenAIEmbeddings()
            
        self.env_id = str(env.spec.id)
        self.memory_by_type = {}
        self.cache_by_type = {}
        self.load_memories()

    def load_memories(self):
        import numpy as np
        for memory_type in ["normal", "aggressive", "conservative"]:
            db_path = f'./db/{self.env_id}/{memory_type}'
            self.memory_by_type[memory_type] = Chroma(
                embedding_function=self.embedding,
                persist_directory=db_path
            )
            self.reload_cache(memory_type)
            try:
                db_size = len(self.cache_by_type[memory_type]['documents'])
            except Exception:
                db_size = 0
            print(f"Loaded memory for {memory_type}, path: {db_path}, cached {db_size} items in RAM.")

    def reload_cache(self, memory_type):
        import numpy as np
        db = self.memory_by_type[memory_type]
        try:
            res = db._collection.get(include=['embeddings', 'documents', 'metadatas'])
            embs = res.get('embeddings', [])
            if embs is not None and len(embs) > 0:
                emb_array = np.array(embs)
            else:
                emb_array = np.empty((0, 768))  # default placeholder dimension
            self.cache_by_type[memory_type] = {
                'embeddings': emb_array,
                'metadatas': res.get('metadatas', []) if res.get('metadatas') else [],
                'documents': res.get('documents', []) if res.get('documents') else [],
                'ids': res.get('ids', []) if res.get('ids') else []
            }
        except Exception as e:
            print(f"Warning: Failed to cache DB {memory_type}: {e}")
            self.cache_by_type[memory_type] = {
                'embeddings': np.empty((0, 768)),
                'metadatas': [],
                'documents': [],
                'ids': []
            }

    def determine_memory_type(self, query_scenario):
        match = re.search(r'Interaction vehicle driving style:\s*(\w+)', query_scenario, re.IGNORECASE)
        if match:
            style = match.group(1).lower()
            if style in ["normal", "aggressive", "conservative"]:
                return style
        return 'normal'

    def retrieveMemory(self, query_scenario, top_k=5):
        """Retrieve the most similar scenarios from the correct partition using slow DB access (kept for backwards compatibility)."""
        memory_type = self.determine_memory_type(query_scenario)
        db = self.memory_by_type[memory_type]
        similarity_results = db.similarity_search_with_score(query_scenario, k=top_k)
        fewshot_results = []
        for idx in range(0, len(similarity_results)):
            fewshot_results.append(similarity_results[idx][0].metadata)
        return fewshot_results

    def retrieveMemory_fast(self, query_scenario, top_k=1):
        """High-speed RAM-based similarity search using NumPy Cosine Similarity (<1ms)."""
        import numpy as np
        memory_type = self.determine_memory_type(query_scenario)
        cache = self.cache_by_type.get(memory_type, None)
        if cache is None or len(cache['documents']) == 0:
            return []
            
        try:
            # 1. Embed query
            query_emb = self.embedding.embed_query(query_scenario)
            query_vector = np.array(query_emb)
            
            # 2. Cosine Similarity
            embs = cache['embeddings']
            norms = np.linalg.norm(embs, axis=1)
            query_norm = np.linalg.norm(query_vector)
            
            if query_norm == 0:
                return []
                
            dot_products = np.dot(embs, query_vector)
            similarities = dot_products / (norms * query_norm + 1e-8)
            
            # 3. Sort indices
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                results.append(cache['metadatas'][idx])
            return results
        except Exception as e:
            print(f"Warning: retrieveMemory_fast failed: {e}")
            return []

    def addMemory(self, sce_descrip, human_question, negotiation, action, comments):
        """Add a new scenario to the correct partitioned database and reload its cache."""
        memory_type = self.determine_memory_type(sce_descrip)
        db = self.memory_by_type[memory_type]
        try:
            doc = Document(page_content=sce_descrip, metadata={"human_question": human_question,
                          'negotiation_result': negotiation, 'final_action': action, 'comments': comments})
            db.add_documents([doc])
            print(f"+++++memory successfully added into {memory_type} dataset+++++")
            self.reload_cache(memory_type)
        except Exception as e:
            print(f"Failed to add scenario: {e}")

    def deleteMemory(self, scenario_id):
        """Delete a scenario from memory by its ID across all partitions."""
        for m_type in ["normal", "aggressive", "conservative"]:
            try:
                if scenario_id in self.memory_by_type[m_type]._collection.ids():
                    self.memory_by_type[m_type].delete([scenario_id])
                    print(f"Deleted scenario with ID {scenario_id} from {m_type}")
                    self.reload_cache(m_type)
            except Exception as e:
                print(f"Failed to delete scenario from {m_type}: {e}")

    def combineMemory(self, other_memory):
        """Combine multiple scenarios into a single memory."""
        for m_type in ["normal", "aggressive", "conservative"]:
            try:
                other_db = other_memory.memory_by_type[m_type]
                other_documents = other_db._collection.get(include=['documents', 'metadatas', 'embeddings'])
                current_db = self.memory_by_type[m_type]
                current_documents = current_db._collection.get(include=['documents', 'metadatas', 'embeddings'])
                for i in range(0, len(other_documents['embeddings'])):
                    if other_documents['embeddings'][i] not in current_documents['embeddings']:
                        current_db._collection.add(
                            embeddings=other_documents['embeddings'][i],
                            metadatas=other_documents['metadatas'][i],
                            documents=other_documents['documents'][i],
                            ids=other_documents['ids'][i]
                        )
                print(f"Merge complete for {m_type}.")
                self.reload_cache(m_type)
            except Exception as e:
                print(f"Failed to combine scenarios for {m_type}: {e}")
