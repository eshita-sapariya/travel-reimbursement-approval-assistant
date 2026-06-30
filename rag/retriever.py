"""
Retrieves relevant policy context.
"""

from rag.vector_store import VectorStore


class PolicyRetriever:

    def __init__(self):

        self.db = VectorStore().load()

    def retrieve(self, query: str, k: int = 1):

        return self.db.similarity_search(query, k=k)

    def retrieve_context(self, query: str, k: int = 3):

        docs = self.retrieve(query, k)

        return "\n\n".join(
            doc.page_content
            for doc in docs
        )