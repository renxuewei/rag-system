"""
LLM routing service
Intelligently selects the most appropriate LLM model based on query scenario
"""

from typing import Dict, Any, Optional, List, AsyncIterator
from enum import Enum
import re
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import config

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """LLM provider"""
    GLM = "glm"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    LOCAL = "local"


class QueryType(str, Enum):
    """Query type"""
    SIMPLE_QA = "simple_qa"           # Simple Q&A
    COMPLEX_REASONING = "complex"     # Complex reasoning
    CODE_GENERATION = "code"          # Code generation
    LONG_CONTEXT = "long_context"     # Long context
    CREATIVE = "creative"             # Creative writing
    SUMMARIZATION = "summary"         # Summarization


class LLMModel:
    """LLM model configuration"""
    
    def __init__(
        self,
        name: str,
        provider: LLMProvider,
        model_id: str,
        api_base: str,
        api_key: str = None,
        max_tokens: int = 4096,
        supports_streaming: bool = True,
        cost_per_1k_tokens: float = 0.001,
        description: str = ""
    ):
        self.name = name
        self.provider = provider
        self.model_id = model_id
        self.api_base = api_base
        self.api_key = api_key or config.OPENAI_API_KEY
        self.max_tokens = max_tokens
        self.supports_streaming = supports_streaming
        self.cost_per_1k_tokens = cost_per_1k_tokens
        self.description = description

        # Lazy initialization of LLM instance
        self._llm_instance = None
    
    def get_llm(self, temperature: float = 0.7) -> ChatOpenAI:
        """Get LLM instance"""
        if self._llm_instance is None:
            self._llm_instance = ChatOpenAI(
                model=self.model_id,
                openai_api_key=self.api_key,
                openai_api_base=self.api_base,
                temperature=temperature,
                streaming=self.supports_streaming,
                max_tokens=self.max_tokens
            )
        return self._llm_instance


class LLMRouter:
    """LLM routing service"""

    def __init__(self):
        # Register available models
        self.models: Dict[str, LLMModel] = {}
        self._loaded_from_db = False

        # Try loading from DB first
        try:
            from app.services.model_config_service import model_config_service
            active_configs = model_config_service.get_active_configs(model_type="llm")
            if active_configs:
                self.reload_models(active_configs)
                self._loaded_from_db = True
        except Exception:
            pass

        if not self._loaded_from_db:
            self._register_default_models()

        # Routing rules
        self.routing_rules = {
            QueryType.SIMPLE_QA: ["glm-3-turbo", "glm-4-flash"],
            QueryType.COMPLEX_REASONING: ["glm-4", "deepseek-chat"],
            QueryType.CODE_GENERATION: ["deepseek-coder", "glm-4"],
            QueryType.LONG_CONTEXT: ["glm-4-long"],
            QueryType.CREATIVE: ["glm-4", "gpt-4"],
            QueryType.SUMMARIZATION: ["glm-4-flash", "glm-3-turbo"],
        }

        # Default model
        self.default_model = "glm-4"

        # Fallback order
        self.fallback_order = ["glm-4", "glm-4-flash", "glm-3-turbo"]

    def _register_default_models(self):
        """Register default models"""
        api_base = config.OPENAI_API_BASE
        api_key = config.OPENAI_API_KEY

        # GLM series
        self.register_model(LLMModel(
            name="glm-4",
            provider=LLMProvider.GLM,
            model_id="glm-4",
            api_base=api_base,
            api_key=api_key,
            max_tokens=4096,
            cost_per_1k_tokens=0.1,
            description="GLM-4 high-quality model, suitable for complex tasks"
        ))

        self.register_model(LLMModel(
            name="glm-4-flash",
            provider=LLMProvider.GLM,
            model_id="glm-4-flash",
            api_base=api_base,
            api_key=api_key,
            max_tokens=4096,
            cost_per_1k_tokens=0.001,
            description="GLM-4-Flash fast model, suitable for simple tasks"
        ))

        self.register_model(LLMModel(
            name="glm-4-long",
            provider=LLMProvider.GLM,
            model_id="glm-4-long",
            api_base=api_base,
            api_key=api_key,
            max_tokens=32768,
            cost_per_1k_tokens=0.05,
            description="GLM-4-Long long context model"
        ))

        self.register_model(LLMModel(
            name="glm-3-turbo",
            provider=LLMProvider.GLM,
            model_id="glm-3-turbo",
            api_base=api_base,
            api_key=api_key,
            max_tokens=4096,
            cost_per_1k_tokens=0.001,
            description="GLM-3-Turbo economical model"
        ))

        # Optional: DeepSeek (if API Key is configured)
        deepseek_key = getattr(config, 'DEEPSEEK_API_KEY', None)
        if deepseek_key:
            self.register_model(LLMModel(
                name="deepseek-chat",
                provider=LLMProvider.DEEPSEEK,
                model_id="deepseek-chat",
                api_base="https://api.deepseek.com/v1",
                api_key=deepseek_key,
                max_tokens=4096,
                cost_per_1k_tokens=0.001,
                description="DeepSeek Chat model"
            ))

            self.register_model(LLMModel(
                name="deepseek-coder",
                provider=LLMProvider.DEEPSEEK,
                model_id="deepseek-coder",
                api_base="https://api.deepseek.com/v1",
                api_key=deepseek_key,
                max_tokens=4096,
                cost_per_1k_tokens=0.001,
                description="DeepSeek Coder code model"
            ))
    
    def register_model(self, model: LLMModel):
        """Register model"""
        self.models[model.name] = model
        logger.info(f"Registered LLM model: {model.name} ({model.provider.value})")

    def reload_models(self, model_configs: list):
        """Reload models from DB configs"""
        self.models.clear()

        for cfg in model_configs:
            model = LLMModel(
                name=cfg["model_id"],
                provider=LLMProvider(cfg.get("provider", "glm")),
                model_id=cfg["model_id"],
                api_base=cfg["api_base"],
                api_key=cfg["api_key"],
                max_tokens=cfg.get("max_tokens", 4096),
                description=cfg.get("description", "")
            )
            self.register_model(model)

        # Update default model
        if self.models:
            self.default_model = next(iter(self.models.keys()))

        # Update fallback order
        self.fallback_order = list(self.models.keys())

        logger.info(f"Reloaded {len(self.models)} models from database")

    def classify_query(self, query: str, context: str = "") -> QueryType:
        """
        Classify query type

        Args:
            query: User query
            context: Context (retrieved documents)

        Returns:
            Query type
        """
        query_lower = query.lower()

        # Code related
        code_patterns = [
            r'\b(code|function|program|implement|write a)'
        ]
        if any(re.search(p, query_lower) for p in code_patterns):
            return QueryType.CODE_GENERATION

        # Long context
        if context and len(context) > 10000:
            return QueryType.LONG_CONTEXT

        # Creative writing
        creative_patterns = [
            r'\b(write|create|generate|story|novel|creative)'
        ]
        if any(re.search(p, query_lower) for p in creative_patterns):
            return QueryType.COMPLEX_REASONING if "analyze" in query_lower else QueryType.CREATIVE

        # Complex reasoning
        complex_patterns = [
            r'\b(analyze|reason|explain|why|how|compare|evaluate|judge)'
        ]
        if any(re.search(p, query_lower) for p in complex_patterns):
            return QueryType.COMPLEX_REASONING

        # Summary
        summary_patterns = [
            r'\b(summarize|summary|brief)'
        ]
        if any(re.search(p, query_lower) for p in summary_patterns):
            return QueryType.SUMMARIZATION

        # Default: simple Q&A
        return QueryType.SIMPLE_QA
    
    def route(
        self,
        query: str,
        context: str = "",
        preferred_model: str = None
    ) -> LLMModel:
        """
        Route to the most suitable model

        Args:
            query: User query
            context: Context
            preferred_model: Specified model (highest priority)

        Returns:
            Selected model
        """
        # 1. If model is specified and exists
        if preferred_model and preferred_model in self.models:
            logger.info(f"Using specified model: {preferred_model}")
            return self.models[preferred_model]

        # 2. Classify query
        query_type = self.classify_query(query, context)

        # 3. Select model based on type
        model_names = self.routing_rules.get(query_type, [self.default_model])

        for model_name in model_names:
            if model_name in self.models:
                logger.info(f"Routing query: {query_type.value} -> {model_name}")
                return self.models[model_name]

        # 4. Use default model
        logger.info(f"Using default model: {self.default_model}")
        return self.models.get(self.default_model)
    
    def generate(
        self,
        query: str,
        context: str = "",
        history: List[Dict[str, str]] = None,
        preferred_model: str = None,
        temperature: float = 0.7
    ) -> str:
        """
        Generate answer (auto routing)

        Args:
            query: User query
            context: Context
            history: Conversation history
            preferred_model: Specified model
            temperature: Temperature
        """
        model = self.route(query, context, preferred_model)
        llm = model.get_llm(temperature)

        # Build messages
        messages = self._build_messages(query, context, history)

        try:
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Model {model.name} call failed: {e}")

            # Try fallback
            return self._fallback_generate(messages, failed_model=model.name, temperature=temperature)
    
    async def generate_stream(
        self,
        query: str,
        context: str = "",
        history: List[Dict[str, str]] = None,
        preferred_model: str = None,
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """
        Stream generation answer (auto routing)
        """
        model = self.route(query, context, preferred_model)
        llm = model.get_llm(temperature)

        messages = self._build_messages(query, context, history)

        try:
            async for chunk in llm.astream(messages):
                yield chunk.content
        except Exception as e:
            logger.error(f"Model {model.name} streaming call failed: {e}")

            # Fallback
            async for chunk in self._fallback_stream(messages, failed_model=model.name, temperature=temperature):
                yield chunk
    
    def _build_messages(
        self,
        query: str,
        context: str,
        history: List[Dict[str, str]] = None
    ) -> List:
        """Build message list"""
        system_prompt = """You are an intelligent assistant responsible for answering user questions based on the knowledge base.

Rules:
1. Answer questions based on the provided reference documents, do not fabricate information
2. If there is no relevant information in the documents, honestly state "No relevant content found in the knowledge base"
3. Cite information sources when answering, format: [Source: Document Name]
4. Keep answers concise, accurate, and highlight key points"""

        if context:
            system_prompt += f"\n\nReference Documents:\n{context}"

        messages = [SystemMessage(content=system_prompt)]

        # Add historical messages
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        # Add current question
        messages.append(HumanMessage(content=query))

        return messages
    
    def _fallback_generate(
        self,
        messages: List,
        failed_model: str,
        temperature: float = 0.7
    ) -> str:
        """Fallback generation"""
        for model_name in self.fallback_order:
            if model_name == failed_model:
                continue
            if model_name in self.models:
                try:
                    logger.info(f"Fallback to model: {model_name}")
                    llm = self.models[model_name].get_llm(temperature)
                    response = llm.invoke(messages)
                    return response.content
                except Exception as e:
                    logger.error(f"Fallback model {model_name} also failed: {e}")
                    continue

        raise RuntimeError("All model calls failed")
    
    async def _fallback_stream(
        self,
        messages: List,
        failed_model: str,
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Fallback streaming generation"""
        for model_name in self.fallback_order:
            if model_name == failed_model:
                continue
            if model_name in self.models:
                try:
                    logger.info(f"Fallback to model: {model_name}")
                    llm = self.models[model_name].get_llm(temperature)
                    async for chunk in llm.astream(messages):
                        yield chunk.content
                    return
                except Exception as e:
                    logger.error(f"Fallback model {model_name} also failed: {e}")
                    continue

        raise RuntimeError("All model calls failed")
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get available models list"""
        return [
            {
                "name": model.name,
                "provider": model.provider.value,
                "description": model.description,
                "max_tokens": model.max_tokens,
                "supports_streaming": model.supports_streaming,
                "cost_per_1k_tokens": model.cost_per_1k_tokens
            }
            for model in self.models.values()
        ]


# Singleton
llm_router = LLMRouter()
