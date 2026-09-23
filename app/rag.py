"""LangGraph RAG pipeline: (rewrite follow-up) -> retrieve -> generate."""
from typing import List

from typing_extensions import TypedDict

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app import config
from app.ingest import get_embeddings

MAX_HISTORY_MESSAGES = 10  # last 5 question/answer pairs are sent to the LLM


class GraphState(TypedDict, total=False):
    question: str               # what the user typed
    search_query: str           # standalone version of the question, used for retrieval
    conversation_history: List[BaseMessage]
    documents: List[Document]
    generation: str


llm = ChatGoogleGenerativeAI(
    model=config.CHAT_MODEL, google_api_key=config.require_api_key(), temperature=0
)

vectorstore = Chroma(
    collection_name=config.COLLECTION_NAME,
    embedding_function=get_embeddings(),
    persist_directory=str(config.CHROMA_DIR),
)

# Turns "What about the maximum amount?" into a standalone question so retrieval works
REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Given the chat history and a follow-up question, rewrite the follow-up as a "
     "standalone question that can be understood without the history. "
     "Return only the rewritten question."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}"),
])
rewrite_chain = REWRITE_PROMPT | llm | StrOutputParser()

GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful HR assistant that answers employee questions about company "
     "policies. Answer only from the context below. If the answer is not in the "
     "context, say you don't know and suggest contacting HR. Be concise and use "
     "bullet points where helpful.\n\nContext:\n{context}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{question}"),
])
generation_chain = GENERATION_PROMPT | llm | StrOutputParser()


def format_docs(docs: List[Document]) -> str:
    return "\n\n---\n\n".join(
        f"[{d.metadata.get('source', 'document')}, page {d.metadata.get('page', 0) + 1}]\n"
        f"{d.page_content}"
        for d in docs
    )


def rewrite(state: GraphState):
    history = state.get("conversation_history", [])
    if not history:
        return {"search_query": state["question"]}
    query = rewrite_chain.invoke(
        {"question": state["question"], "chat_history": history[-MAX_HISTORY_MESSAGES:]}
    )
    return {"search_query": query.strip() or state["question"]}


def retrieve(state: GraphState):
    docs = vectorstore.similarity_search(state["search_query"], k=config.TOP_K)
    return {"documents": docs}


def generate(state: GraphState):
    history = state.get("conversation_history", [])
    answer = generation_chain.invoke({
        "question": state["question"],
        "context": format_docs(state["documents"]),
        "chat_history": history[-MAX_HISTORY_MESSAGES:],
    })
    return {
        "generation": answer,
        "conversation_history": history
        + [HumanMessage(content=state["question"]), AIMessage(content=answer)],
    }


workflow = StateGraph(GraphState)
workflow.add_node("rewrite", rewrite)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate)
workflow.set_entry_point("rewrite")
workflow.add_edge("rewrite", "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)

# MemorySaver keeps each session's history (keyed by thread_id) in RAM.
graph = workflow.compile(checkpointer=MemorySaver())


def ask(question: str, session_id: str) -> dict:
    """Run one chat turn. History for session_id is kept by the checkpointer."""
    result = graph.invoke(
        {"question": question},
        config={"configurable": {"thread_id": session_id}},
    )
    sources = [
        {
            "source": d.metadata.get("source", "document"),
            "page": d.metadata.get("page", 0) + 1,
            "snippet": d.page_content[:300],
        }
        for d in result.get("documents", [])
    ]
    return {"answer": result["generation"], "sources": sources}


def document_count() -> int:
    return vectorstore._collection.count()
