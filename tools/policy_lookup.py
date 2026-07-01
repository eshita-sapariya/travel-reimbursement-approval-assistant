from langchain.tools import tool
from rag.retriever import PolicyRetriever

retriever = PolicyRetriever()


@tool
def policy_lookup(query: str) -> str:
    """
    Retrieve relevant travel reimbursement policy
    based on the user query.
    """

    return retriever.retrieve_context(query)