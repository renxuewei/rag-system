"""
Model configuration service
Supports database configuration management for LLM and Embedding models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import logging
import time
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.services.metadata import Base, metadata_service, ModelConfig

logger = logging.getLogger(__name__)


class ModelConfigService:
    """Model configuration service"""

    def __init__(self):
        """Initialize model configuration service, reuse metadata service database connection"""
        self.engine = metadata_service.engine
        self.SessionLocal = metadata_service.SessionLocal

    def get_db(self) -> Optional[Session]:
        """Get database session"""
        if not self.SessionLocal:
            return None
        return self.SessionLocal()

    def _mask_api_key(self, api_key: str) -> str:
        """Mask API key for display: 'sk-abc...xyz' -> 'sk-***xyz'"""
        if not api_key or len(api_key) <= 8:
            return "***"
        return api_key[:3] + "***" + api_key[-3:]

    def create_model_config(
        self,
        id: str,
        name: str,
        provider: str,
        model_id: str,
        api_base: str,
        api_key: str,
        model_type: str = "llm",
        max_tokens: int = 4096,
        is_default: bool = False,
        description: str = None
    ) -> Optional[Dict]:
        """
        Create a model config. If is_default=True, unset other defaults of same model_type.
        """
        db = self.get_db()
        if not db:
            return None

        try:
            # If setting is_default=True, unset other defaults first
            if is_default:
                db.query(ModelConfig).filter(
                    ModelConfig.model_type == model_type,
                    ModelConfig.is_default == True
                ).update({"is_default": False})

            config = ModelConfig(
                id=id,
                name=name,
                provider=provider,
                model_id=model_id,
                api_base=api_base,
                api_key=api_key,
                model_type=model_type,
                max_tokens=max_tokens,
                is_default=is_default,
                description=description
            )
            db.add(config)
            db.commit()

            logger.info(f"Created model configuration: {id} (name={name}, type={model_type})")

            return {
                "id": config.id,
                "name": config.name,
                "provider": config.provider,
                "model_id": config.model_id,
                "api_base": config.api_base,
                "api_key_masked": self._mask_api_key(config.api_key),
                "model_type": config.model_type,
                "max_tokens": config.max_tokens,
                "is_active": config.is_active,
                "is_default": config.is_default,
                "description": config.description,
                "created_at": config.created_at.isoformat() if config.created_at else None
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create model configuration: {e}")
            return None
        finally:
            db.close()

    def get_model_config(self, config_id: str) -> Optional[Dict]:
        """
        Get config by ID. Return dict with api_key_masked (NOT the real key).
        """
        db = self.get_db()
        if not db:
            return None

        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
            if config:
                return {
                    "id": config.id,
                    "name": config.name,
                    "provider": config.provider,
                    "model_id": config.model_id,
                    "api_base": config.api_base,
                    "api_key_masked": self._mask_api_key(config.api_key),
                    "model_type": config.model_type,
                    "max_tokens": config.max_tokens,
                    "is_active": config.is_active,
                    "is_default": config.is_default,
                    "description": config.description,
                    "created_at": config.created_at.isoformat() if config.created_at else None,
                    "updated_at": config.updated_at.isoformat() if config.updated_at else None
                }
            return None
        finally:
            db.close()

    def list_model_configs(
        self,
        model_type: str = None,
        active_only: bool = False
    ) -> List[Dict]:
        """
        List configs. Always return api_key_masked.
        """
        db = self.get_db()
        if not db:
            return []

        try:
            query = db.query(ModelConfig)
            if model_type:
                query = query.filter(ModelConfig.model_type == model_type)
            if active_only:
                query = query.filter(ModelConfig.is_active == True)

            configs = query.order_by(ModelConfig.created_at.desc()).all()

            return [
                {
                    "id": config.id,
                    "name": config.name,
                    "provider": config.provider,
                    "model_id": config.model_id,
                    "api_base": config.api_base,
                    "api_key_masked": self._mask_api_key(config.api_key),
                    "model_type": config.model_type,
                    "max_tokens": config.max_tokens,
                    "is_active": config.is_active,
                    "is_default": config.is_default,
                    "description": config.description,
                    "created_at": config.created_at.isoformat() if config.created_at else None,
                    "updated_at": config.updated_at.isoformat() if config.updated_at else None
                }
                for config in configs
            ]
        finally:
            db.close()

    def update_model_config(self, config_id: str, **kwargs) -> bool:
        """
        Update config fields. If setting is_default=True, unset others first.
        """
        db = self.get_db()
        if not db:
            return False

        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
            if not config:
                return False

            # If setting is_default=True, unset other defaults first
            if kwargs.get("is_default") == True:
                model_type = kwargs.get("model_type", config.model_type)
                db.query(ModelConfig).filter(
                    ModelConfig.model_type == model_type,
                    ModelConfig.is_default == True,
                    ModelConfig.id != config_id
                ).update({"is_default": False})

            # Update fields
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            config.updated_at = datetime.utcnow()
            db.commit()

            logger.info(f"Updated model configuration: {config_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update model configuration: {e}")
            return False
        finally:
            db.close()

    def delete_model_config(self, config_id: str) -> bool:
        """
        Soft delete: set is_active=False (per AGENTS.md soft delete rule).
        """
        db = self.get_db()
        if not db:
            return False

        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
            if config:
                config.is_active = False
                config.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Soft deleted model configuration: {config_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete model configuration: {e}")
            return False
        finally:
            db.close()

    def get_default_config(self, model_type: str = "llm") -> Optional[Dict]:
        """
        Get the default active config for a model type. Return dict WITH real api_key.
        """
        db = self.get_db()
        if not db:
            return None

        try:
            config = db.query(ModelConfig).filter(
                ModelConfig.model_type == model_type,
                ModelConfig.is_default == True,
                ModelConfig.is_active == True
            ).first()

            if config:
                return {
                    "id": config.id,
                    "name": config.name,
                    "provider": config.provider,
                    "model_id": config.model_id,
                    "api_base": config.api_base,
                    "api_key": config.api_key,  # Return real key for internal use
                    "model_type": config.model_type,
                    "max_tokens": config.max_tokens,
                    "description": config.description
                }
            return None
        finally:
            db.close()

    def get_active_configs(self, model_type: str = None) -> List[Dict]:
        """
        Get all active configs. Return dicts WITH real api_key (for internal service use).
        """
        db = self.get_db()
        if not db:
            return []

        try:
            query = db.query(ModelConfig).filter(ModelConfig.is_active == True)
            if model_type:
                query = query.filter(ModelConfig.model_type == model_type)

            configs = query.all()

            return [
                {
                    "id": config.id,
                    "name": config.name,
                    "provider": config.provider,
                    "model_id": config.model_id,
                    "api_base": config.api_base,
                    "api_key": config.api_key,  # Return real key for internal use
                    "model_type": config.model_type,
                    "max_tokens": config.max_tokens,
                    "description": config.description,
                    "is_default": config.is_default
                }
                for config in configs
            ]
        finally:
            db.close()

    def test_connection(self, config_id: str) -> Dict:
        """
        Test model connectivity by making a simple API call. Return {success, error, latency_ms}.
        """
        db = self.get_db()
        if not db:
            return {"success": False, "error": "Database connection failed", "latency_ms": 0}

        try:
            config = db.query(ModelConfig).filter(ModelConfig.id == config_id).first()
            if not config:
                return {"success": False, "error": "Configuration does not exist", "latency_ms": 0}

            if not config.is_active:
                return {"success": False, "error": "Configuration is disabled", "latency_ms": 0}

            start_time = time.time()

            try:
                if config.model_type == "llm":
                    # Test LLM connection
                    llm = ChatOpenAI(
                        model=config.model_id,
                        openai_api_key=config.api_key,
                        openai_api_base=config.api_base,
                        temperature=0.1,
                        max_tokens=10
                    )
                    # Simple test call
                    response = llm.invoke("Hi")
                    if response.content:
                        latency_ms = (time.time() - start_time) * 1000
                        logger.info(f"LLM connection test successful: {config.name} ({latency_ms:.2f}ms)")
                        return {"success": True, "error": None, "latency_ms": round(latency_ms, 2)}

                elif config.model_type == "embedding":
                    # Test Embedding connection
                    embeddings = OpenAIEmbeddings(
                        model=config.model_id,
                        openai_api_key=config.api_key,
                        openai_api_base=config.api_base
                    )
                    # Simple test call
                    result = embeddings.embed_query("test")
                    if result:
                        latency_ms = (time.time() - start_time) * 1000
                        logger.info(f"Embedding connection test successful: {config.name} ({latency_ms:.2f}ms)")
                        return {"success": True, "error": None, "latency_ms": round(latency_ms, 2)}

                return {"success": False, "error": "Unknown model type", "latency_ms": 0}

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                error_msg = f"Connection failed: {str(e)}"
                logger.error(f"Model connection test failed: {config.name}, error: {e}")
                return {"success": False, "error": error_msg, "latency_ms": round(latency_ms, 2)}

        finally:
            db.close()


# Singleton
model_config_service = ModelConfigService()
