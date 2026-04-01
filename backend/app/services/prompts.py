"""
Prompt template management
"""

from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PromptTemplates:
    """Prompt template collection"""
    
    # RAG Q&A template
    RAG_QA = ChatPromptTemplate.from_messages([
        ("system", """You are an intelligent assistant responsible for answering user questions based on the knowledge base.

Rules:
1. Answer questions based on the provided reference documents, do not fabricate information
2. If there is no relevant information in the documents, honestly state "No relevant content found in the knowledge base"
3. Cite information sources when answering, format: [Source: Document Name]
4. Keep answers concise, accurate, and highlight key points

Reference Documents:
{context}

Current Time: {current_time}"""),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}")
    ])

    # Query rewrite template
    QUERY_REWRITE = ChatPromptTemplate.from_messages([
        ("system", """You are a query optimization assistant.

Task: Rewrite colloquial user questions into a form more suitable for retrieval.

Rules:
1. Retain the core intent of the original question
2. Add necessary keywords
3. Fix grammatical errors
4. Keep it concise

Output only the rewritten question, do not explain."""),
        ("human", "Original Question: {query}\n\nPlease rewrite:")
    ])

    # Document summary template
    DOC_SUMMARY = ChatPromptTemplate.from_messages([
        ("system", "You are a document summary assistant. Please generate a concise summary for the following document, highlighting key information."),
        ("human", "Document Content:\n{content}\n\nPlease generate summary:")
    ])

    # Rejection template
    REJECT = ChatPromptTemplate.from_messages([
        ("system", "You are an honest assistant. If there is no relevant information in the knowledge base, honestly inform the user."),
        ("human", "{question}")
    ])

    # Multi-turn conversation compression template
    COMPRESS_HISTORY = ChatPromptTemplate.from_messages([
        ("system", """You are a conversation compression assistant.

Task: Compress multi-turn conversation history into a concise summary, preserving key information.

Rules:
1. Retain the user's core questions and requirements
2. Retain key information provided by the assistant
3. Omit duplicate and irrelevant content
4. Maintain summary completeness

Output only the compressed summary."""),
        ("human", "Conversation History:\n{history}\n\nPlease compress:")
    ])


def format_rag_prompt(
    question: str,
    context: str,
    history: List[Dict[str, str]] = None,
    current_time: str = ""
) -> str:
    """
    Format RAG Prompt
    Args:
        question: User question
        context: Retrieved context
        history: Conversation history
        current_time: Current time
    """
    from datetime import datetime

    if not current_time:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    messages = PromptTemplates.RAG_QA.format_messages(
        context=context,
        current_time=current_time,
        history=history or [],
        question=question
    )

    return messages


def format_query_rewrite(query: str) -> str:
    """Format query rewrite prompt"""
    messages = PromptTemplates.QUERY_REWRITE.format_messages(query=query)
    return messages


def format_doc_summary(content: str) -> str:
    """Format document summary prompt"""
    messages = PromptTemplates.DOC_SUMMARY.format_messages(content=content)
    return messages


def format_compress_history(history: str) -> str:
    """Format history compression prompt"""
    messages = PromptTemplates.COMPRESS_HISTORY.format_messages(history=history)
    return messages
