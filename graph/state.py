from typing import TypedDict


class AgentState(TypedDict):

    messages: list          # UI chat history — plain dicts with role/content

    agent_messages: list    # ReAct loop messages — LangChain BaseMessage objects

    claim: dict             # accumulated claim fields across turns

    final_answer: str

    audit_trail: list
