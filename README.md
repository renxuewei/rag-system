# RAG Knowledge Base System

Enterprise-grade Retrieval-Augmented Generation (RAG) system built with FastAPI, Milvus, and LangChain. Supports multi-tenant document management, hybrid retrieval, streaming responses, and Kubernetes-native deployment.

## Features

- **Document Processing** — Parse PDF, Word, Markdown, and TXT files with configurable chunking strategies
- **Hybrid Retrieval** — Combine BM25 keyword search with Milvus vector similarity, fused via Reciprocal Rank Fusion (RRF)
- **Multi-Tenant Isolation** — Partition-based tenant isolation in Milvus with tenant-aware metadata in PostgreSQL
- **Streaming Responses** — Real-time token streaming for interactive Q&A experience
- **Conversation Management** — Persistent chat history with auto-generated titles and tagging
- **Document Review Workflow** — Multi-stage review pipeline with task assignment and batch operations
- **User Feedback System** — Rating, comment, and low-score alerting for answer quality tracking
- **Model Configuration** — Dynamic LLM and embedding model switching via database-backed configuration
- **Answer Caching** — Redis-backed semantic answer caching with optional warmup on startup
- **Security** — JWT authentication, role-based access control (RBAC), PII detection, and sensitive content filtering
- **Observability** — Prometheus metrics, structured logging, and audit trail for all operations
- **Kubernetes Ready** — Full K8s manifests with HPA autoscaling, ConfigMaps, Secrets, and monitoring stack

## UI

<div align="center">
  <img src="./assets/chat.png" alt="chat" width="80%">
  <img src="./assets/model-management.png" alt="model" width="80%">
  <img src="./assets/doc-management.png" alt="doc" width="80%">
</div>

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / Frontend                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                     FastAPI (RAG API)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐ │
│  │   Auth   │ │  Users   │ │Documents │ │  Conversations    │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐ │
│  │  Query   │ │  Review  │ │ Feedback │ │  Model Config     │ │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘ │
└────────────┬──────────────────────────┬────────────────────────┘
             │                          │
┌────────────▼──────────┐  ┌────────────▼────────────────────────┐
│    Core Services      │  │        External Services            │
│ ┌───────────────────┐ │  │  ┌──────────────────────────────┐  │
│ │ Document Processor│ │  │  │  Milvus (Vector DB)          │  │
│ │ Embedding Service │ │  │  │  PostgreSQL (Metadata)       │  │
│ │ Retriever (Hybrid)│ │  │  │  Redis (Cache)               │  │
│ │ Reranker          │ │  │  │  MinIO (Object Storage)      │  │
│ │ LLM Service       │ │  │  │  LLM API (GLM-4 / OpenAI)    │  │
│ │ Stream Service    │ │  │  └──────────────────────────────┘  │
│ │ Cache Service     │ │                                      │
│ │ PII Detector      │ │                                      │
│ │ Sensitive Filter  │ │                                      │
│ └───────────────────┘ │                                      │
└───────────────────────┘                                      │
```

## Tech Stack

| Category | Technology |
|---|---|
| **Framework** | FastAPI 0.104+, Uvicorn, Pydantic 2.5+ |
| **LLM Orchestration** | LangChain 0.1+, LangGraph |
| **Vector Database** | Milvus 2.3+ |
| **Relational DB** | PostgreSQL (via SQLAlchemy 2.0+) |
| **Cache** | Redis 5.0+ |
| **Object Storage** | MinIO |
| **Embedding** | BGE-M3 / OpenAI-compatible APIs |
| **Retrieval** | BM25 (rank-bm25) + Jieba (Chinese segmentation) |
| **Authentication** | PyJWT (HS256) |
| **Monitoring** | Prometheus Client |
| **Deployment** | Kubernetes (HPA, ConfigMap, Secrets) |
| **Python Version** | 3.11+ |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL, Redis, Milvus, MinIO (or use the K8s manifests)

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
# or with Poetry
poetry install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Key environment variables:

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | LLM API key | — |
| `OPENAI_API_BASE` | LLM API endpoint | `https://open.bigmodel.cn/api/paas/v4` |
| `POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `REDIS_HOST` | Redis host | `localhost` |
| `MILVUS_HOST` | Milvus host | `localhost` |
| `MINIO_ENDPOINT` | MinIO endpoint | `localhost:9000` |
| `JWT_SECRET_KEY` | JWT signing key | — |
| `LLM_MODEL_NAME` | Default LLM model | `glm-4` |
| `EMBEDDING_MODEL_NAME` | Default embedding model | `embedding-3` |
| `CHUNK_SIZE` | Document chunk size | `500` |
| `TOP_K` | Retrieval top-k results | `5` |

### 3. Start the Server

```bash
cd backend
python -m app.main
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`.

### 4. API Documentation

Interactive API docs are available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | User login, returns JWT token |
| `GET` | `/api/auth/verify` | Verify token validity |

### User Management
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/users` | List all users (tenant-scoped) |
| `POST` | `/api/users` | Create user (admin only) |
| `GET` | `/api/users/{user_id}` | Get user details |
| `PUT` | `/api/users/{user_id}` | Update user |
| `DELETE` | `/api/users/{user_id}` | Delete user |
| `POST` | `/api/users/{user_id}/reset-password` | Reset password |
| `GET` | `/api/roles` | List available roles |

### Knowledge Base Query
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/query` | Standard query (returns answer + sources) |
| `POST` | `/api/query/stream` | Streaming query (SSE) |

### Document Management
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents` | Upload document (PDF/DOCX/MD/TXT) |
| `GET` | `/api/documents` | List uploaded documents |
| `DELETE` | `/api/documents/{doc_id}` | Delete document |

### Category Management
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/categories` | Create category |
| `GET` | `/api/categories` | List categories |
| `GET` | `/api/categories/{category_id}` | Get category details |
| `PUT` | `/api/categories/{category_id}` | Update category |
| `DELETE` | `/api/categories/{category_id}` | Delete category |
| `POST` | `/api/documents/{doc_id}/categories` | Assign category to document |
| `DELETE` | `/api/documents/{doc_id}/categories/{category_id}` | Remove category from document |

### Review Workflow
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/reviews` | Create review |
| `GET` | `/api/reviews` | List reviews |
| `PUT` | `/api/reviews/{review_id}` | Update review status |
| `POST` | `/api/reviews/batch` | Batch update reviews |
| `POST` | `/api/review-tasks` | Create review task |
| `GET` | `/api/review-tasks` | List review tasks |

### Feedback
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/feedback` | Submit answer feedback |
| `GET` | `/api/feedback/stats` | Get feedback statistics |
| `GET` | `/api/feedback/low-rating` | Get low-rating feedback list |
| `GET` | `/api/feedback/trend` | Get feedback trend data |

### Conversations
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/conversations` | Create conversation |
| `GET` | `/api/conversations` | List user conversations |
| `GET` | `/api/conversations/{conv_id}` | Get conversation details |
| `GET` | `/api/conversations/{conv_id}/messages` | Get conversation messages |
| `POST` | `/api/conversations/{conv_id}/messages` | Add message to conversation |
| `DELETE` | `/api/conversations/{conv_id}` | Delete conversation |
| `PUT` | `/api/conversations/{conv_id}/archive` | Archive/unarchive conversation |
| `PUT` | `/api/conversations/{conv_id}/tags` | Update conversation tags |

### Model Configuration
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/model-configs` | List model configurations |
| `POST` | `/api/model-configs` | Create model configuration |
| `GET` | `/api/model-configs/{config_id}` | Get configuration details |
| `PUT` | `/api/model-configs/{config_id}` | Update configuration |
| `DELETE` | `/api/model-configs/{config_id}` | Delete configuration |
| `POST` | `/api/model-configs/{config_id}/test` | Test model connection |

### System
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/stats` | System statistics |
| `GET` | `/api/health` | Health check |
| `GET` | `/health` | Service health check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/audit-logs` | Audit log query |

## Project Structure

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application entry point
│   │   ├── config.py               # Configuration management
│   │   ├── routers/
│   │   │   └── api.py              # All API route handlers (49 endpoints)
│   │   ├── services/
│   │   │   ├── document_processor.py   # Document parsing & chunking
│   │   │   ├── embeddings.py           # Text embedding service
│   │   │   ├── vector_store.py         # Milvus vector operations
│   │   │   ├── retriever.py            # Hybrid retrieval (BM25 + Vector + RRF)
│   │   │   ├── reranker.py             # Cross-encoder reranking
│   │   │   ├── llm.py                  # LLM inference service
│   │   │   ├── llm_router.py           # Multi-model routing
│   │   │   ├── stream.py               # Streaming response generator
│   │   │   ├── cache.py                # Redis cache service
│   │   │   ├── answer_cache.py         # Semantic answer caching
│   │   │   ├── cache_warmup.py         # Startup cache warmup
│   │   │   ├── metadata.py             # PostgreSQL metadata & user management
│   │   │   ├── storage.py              # MinIO object storage
│   │   │   ├── conversation.py         # Chat history management
│   │   │   ├── review.py               # Document review workflow
│   │   │   ├── feedback.py             # User feedback collection
│   │   │   ├── model_config_service.py # Dynamic model configuration
│   │   │   ├── prompts.py              # Prompt templates
│   │   │   ├── tenant.py               # Multi-tenant context
│   │   │   ├── pii_detector.py         # PII detection
│   │   │   ├── sensitive_filter.py     # Sensitive content filtering
│   │   │   ├── deduplication.py        # Document deduplication
│   │   │   └── ingestion/
│   │   │       ├── api_fetcher.py      # REST API data ingestion
│   │   │       ├── crawler.py          # Web crawler ingestion
│   │   │       ├── db_sync.py          # Database sync ingestion
│   │   │       └── base.py             # Base ingestion class
│   │   └── utils/
│   │       ├── auth.py                 # JWT authentication & RBAC
│   │       ├── validators.py           # Input validation
│   │       ├── rate_limit.py           # Rate limiting
│   │       ├── metrics.py              # Prometheus metrics
│   │       └── audit.py                # Audit logging
│   ├── requirements.txt
│   └── pyproject.toml
├── k8s/
│   ├── configmap.yaml                  # Application configuration
│   ├── secrets.yaml                    # Sensitive credentials
│   ├── hpa.yaml                        # Horizontal Pod Autoscaler
│   ├── prometheus-alerts.yaml          # Prometheus alerting rules
│   ├── grafana-alertmanager-config.yaml # Alertmanager routing
│   └── deployments/
│       └── milvus.yaml                 # Milvus deployment
├── .env.example                        # Environment template
└── README.md
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (Minikube or production)
- Helm (optional, for Prometheus/Grafana)

### Deploy

```bash
# Apply secrets and configuration
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml

# Deploy Milvus
kubectl apply -f k8s/deployments/milvus.yaml

# Deploy remaining services (rag-api deployment manifest required)
# kubectl apply -f k8s/deployments/rag-api.yaml

# Apply autoscaling
kubectl apply -f k8s/hpa.yaml

# Set up monitoring
kubectl apply -f k8s/prometheus-alerts.yaml
kubectl apply -f k8s/grafana-alertmanager-config.yaml
```

### Monitoring

The system exposes Prometheus metrics at `/metrics` including:
- Request rate, latency, and error rates
- Cache hit/miss ratios
- Active connection counts
- Vector store size
- Query success rates
- Document operation counts

Pre-configured alert rules cover error rates, latency thresholds, resource utilization, and pod health.

## Development

### Run Tests

```bash
cd backend
pytest
```

### Code Style

```bash
black backend/app/
flake8 backend/app/
```

## License

MIT
