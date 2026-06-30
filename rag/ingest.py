import os

from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY_FILE = os.path.join(BASE_DIR, "data", "travel_policy.md")
VECTOR_DB_PATH = os.path.join(BASE_DIR, "faiss_index")


def create_vector_store():

    print("[ingest] Loading policy document...")

    loader = TextLoader(POLICY_FILE, encoding="utf-8")
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
    )
    chunks = splitter.split_documents(docs)

    print(f"[ingest] Created {len(chunks)} chunks.")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(VECTOR_DB_PATH)

    print("[ingest] FAISS index created and saved.")


if __name__ == "__main__":
    create_vector_store()