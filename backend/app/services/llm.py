"""
LLM service
Integrates GLM-4 large language model
"""

from typing import List, Dict, Any, Optional, AsyncIterator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.config import config


class LLMService:
    """LLM service"""
    
    def __init__(
        self,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.7
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.llm = None

        # Try loading from DB first, fall back to env vars
        self._init_config()

        # Create LLM instance
        self.llm = ChatOpenAI(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=self.temperature,
            streaming=True
        )

    def _init_config(self):
        """Initialize config from DB or env vars"""
        try:
            from app.services.model_config_service import model_config_service
            default_config = model_config_service.get_default_config(model_type="llm")
            if default_config:
                if not self.model_name:
                    self.model_name = default_config["model_id"]
                if not self.api_key:
                    self.api_key = default_config["api_key"]
                if not self.base_url:
                    self.base_url = default_config["api_base"]
        except Exception:
            pass

        # Fall back to env vars
        if not self.model_name:
            self.model_name = config.LLM_MODEL_NAME
        if not self.api_key:
            self.api_key = config.OPENAI_API_KEY
        if not self.base_url:
            self.base_url = config.OPENAI_API_BASE

    def reconfigure(
        self,
        model_name: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = None
    ):
        """Reconfigure the LLM with new settings"""
        if model_name:
            self.model_name = model_name
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        if temperature is not None:
            self.temperature = temperature

        # Re-create the LLM instance
        self.llm = ChatOpenAI(
            model=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=self.temperature,
            streaming=True
        )
    
    def generate(self, prompt: str) -> str:
        """
        Simple text generation
        Args:
            prompt: Input prompt
        """
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def chat(
        self,
        query: str,
        context: str = "",
        history: List[Dict[str, str]] = None
    ) -> str:
        """
        Chat generation
        Args:
            query: User question
            context: Context (retrieved documents)
            history: Chat history
        """
        # Build prompt
        system_prompt = """You are an intelligent assistant responsible for answering user questions based on the knowledge base.

Rules:
1. Answer questions based on the provided reference documents
2. If there is no relevant information in the documents, please truthfully state "No relevant content found in the knowledge base"
3. Mark information sources when answering
4. Keep answers concise and accurate"""

        if context:
            system_prompt += f"\n\nReference docs:\n{context}"

        # Build messages
        messages = [SystemMessage(content=system_prompt)]

        # Add history messages
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        # Add current question
        messages.append(HumanMessage(content=query))

        # Call LLM
        response = self.llm.invoke(messages)

        return response.content
    
    async def chat_stream(
        self,
        query: str,
        context: str = "",
        history: List[Dict[str, str]] = None
    ) -> AsyncIterator[Dict[str, str]]:
        """
        Streaming chat generation, auto-detect and separate thinking/content
        Args:
            query: User question
            context: Context
            history: Chat history
        Yields:
            {"type": "thinking", "content": "..."} or {"type": "content", "content": "..."}
        """
        system_prompt = """You are an intelligent assistant responsible for answering user questions based on the knowledge base.

Rules:
1. Answer questions based on the provided reference documents
2. If there is no relevant information in the documents, please truthfully state "No relevant content found in the knowledge base"
3. Mark information sources when answering
4. Keep answers concise and accurate"""

        if context:
            system_prompt += f"\n\nReference docs:\n{context}"

        messages = [SystemMessage(content=system_prompt)]

        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=query))

        in_thinking = False
        buffer = ""

        async for chunk in self.llm.astream(messages):
            text = chunk.content
            if not text:
                continue

            buffer += text

            while buffer:
                if not in_thinking:
                    open_idx = buffer.find("<think")
                    if open_idx == -1:
                        safe = buffer
                        buffer = ""
                        if safe:
                            yield {"type": "content", "content": safe}
                        break
                    else:
                        if open_idx > 0:
                            yield {"type": "content", "content": buffer[:open_idx]}
                        rest = buffer[open_idx:]
                        close_tag_idx = rest.find(">")
                        if close_tag_idx == -1:
                            buffer = rest
                            break
                        buffer = rest[close_tag_idx + 1:]
                        in_thinking = True
                else:
                    close_idx = buffer.find("</think")
                    if close_idx == -1:
                        thinking_chunk = buffer
                        buffer = ""
                        if thinking_chunk:
                            yield {"type": "thinking", "content": thinking_chunk}
                        break
                    else:
                        thinking_chunk = buffer[:close_idx]
                        if thinking_chunk:
                            yield {"type": "thinking", "content": thinking_chunk}
                        rest = buffer[close_idx:]
                        close_tag_end = rest.find(">")
                        if close_tag_end == -1:
                            buffer = rest
                            break
                        buffer = rest[close_tag_end + 1:]
                        in_thinking = False

        if buffer:
            if in_thinking:
                yield {"type": "thinking", "content": buffer}
            else:
                yield {"type": "content", "content": buffer}
    
    def build_rag_prompt(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> str:
        """
        Build RAG Prompt
        Args:
            query: User question
            documents: List of retrieved documents
        """
        # Concatenate document content
        context_parts = []
        for i, doc in enumerate(documents):
            source = doc.get("source", "Unknown source")
            content = doc.get("content", "")
            context_parts.append(f"[Doc{i+1}] Source: {source}\n{content}")

        context = "\n\n".join(context_parts)

        prompt = f"""Answer the user's question based on the following reference documents.

Reference documents:
{context}

User question: {query}

Please answer the question based on the reference documents and mark information sources. If there is no relevant information in the documents, please truthfully state it."""

        return prompt


# Singleton
llm_service = LLMService()
