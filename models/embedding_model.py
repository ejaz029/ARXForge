import os
import warnings
import logging
from langchain_huggingface import HuggingFaceEmbeddings  # Free embeddings
from langchain_community.vectorstores import FAISS
from config.device_utils import get_device, get_device_name

# Suppress TensorFlow warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger('tensorflow').setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")

class EmbeddingModel:
    def __init__(self):
        """Initialize the embedding model using HuggingFace embeddings with automatic GPU detection."""
        device = get_device()
        self.embeddings = HuggingFaceEmbeddings(
            model_kwargs={"device": device}
        )
        self.vector_db = None
        print(f"EmbeddingModel initialized on {get_device_name()}")

    def build_vector_db(self, texts):
        """
        Creates a FAISS vector database from a list of text chunks.
        """
        self.vector_db = FAISS.from_texts(texts, self.embeddings)

    def retrieve_similar_texts(self, query, top_k=3):
        """
        Retrieves the top-k most similar ARXML text chunks based on query.
        """
        if not self.vector_db:
            return ["⚠️ Vector database is not initialized."]
        
        docs = self.vector_db.similarity_search(query, k=top_k)
        return [doc.page_content for doc in docs]

# Example Usage
if __name__ == "__main__":
    model = EmbeddingModel()
    
    sample_texts = [
        "ARXML defines software components in an ECU.",
        "P-PORT and R-PORT must have matching data types.",
        "UUIDs must be unique for each entity.",
    ]
    
    model.build_vector_db(sample_texts)
    results = model.retrieve_similar_texts("Check UUID uniqueness.")
    
    print("🔍 Similar Texts Found:")
    for res in results:
        print(f"- {res}")
