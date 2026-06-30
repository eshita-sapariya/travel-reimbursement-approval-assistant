import os

from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DB_PATH = os.path.join(BASE_DIR, "faiss_index")


class VectorStore:

    def __init__(self):

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    def load(self):

        if not os.path.exists(VECTOR_DB_PATH):
            print("[vector_store] FAISS index not found — running ingest...")
            from rag.ingest import create_vector_store
            create_vector_store()

        return FAISS.load_local(
            VECTOR_DB_PATH,
            self.embeddings,
            allow_dangerous_deserialization=True,
        )