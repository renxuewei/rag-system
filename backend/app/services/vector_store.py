"""
Milvus vector store service
Supports multi-tenant isolation (Partition)
"""

from typing import List, Dict, Any, Optional
from pymilvus import (
    connections,
    Collection,
    Partition,
    FieldSchema,
    CollectionSchema,
    DataType,
    utility
)
import logging

from app.config import config
from app.services.embeddings import embedding_service

logger = logging.getLogger(__name__)


class MilvusService:
    """Milvus vector store service (supports multi-tenancy)"""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = "rag_documents"
    ):
        self.host = host or config.MILVUS_HOST
        self.port = port or config.MILVUS_PORT
        self.collection_name = collection_name
        self.collection = None

        # Vector dimension (embedding-3 model dimension is 2048)
        self.embedding_dim = 2048

        # Tenant partition cache
        self._tenant_partitions: Dict[str, bool] = {}
    
    def _get_tenant_id(self, tenant_id: str = None) -> str:
        """Get tenant ID"""
        if tenant_id:
            return tenant_id

        # Try to get from context
        from app.services.tenant import get_tenant_id
        ctx_tenant_id = get_tenant_id()
        if ctx_tenant_id:
            return ctx_tenant_id

        return "default"
    
    def _get_partition_name(self, tenant_id: str) -> str:
        """
        Get tenant partition name

        Args:
            tenant_id: Tenant ID

        Returns:
            Partition name
        """
        # Replace special characters to ensure valid partition name
        safe_id = tenant_id.replace("-", "_").replace(".", "_")
        return f"tenant_{safe_id}"
    
    def connect(self):
        """Connect to Milvus"""
        connections.connect(
            alias="default",
            host=self.host,
            port=self.port
        )
        logger.info(f"✅ Connected to Milvus: {self.host}:{self.port}")
    
    def disconnect(self):
        """Disconnect"""
        connections.disconnect("default")
    
    def create_collection(self):
        """Create collection"""
        # If collection exists, check if it has content_hash field, drop and recreate if not
        if utility.has_collection(self.collection_name):
            logger.info(f"⚠️ Collection already exists: {self.collection_name}")
            self.collection = Collection(self.collection_name)

            # Check if content_hash field exists
            schema = self.collection.schema
            field_names = [field.name for field in schema.fields]

            if "content_hash" not in field_names:
                logger.warning("⚠️ Collection missing content_hash field, will drop and recreate")
                utility.drop_collection(self.collection_name)
                # Continue to create new collection
            else:
                logger.info("✅ Collection structure is correct")
                # Create default tenant partition
                self._ensure_partition("default")
                return

        # Define fields (add tenant_id)
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=5000),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="content_hash", dtype=DataType.VARCHAR, max_length=64),  # For deduplication
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        ]

        # Create collection
        schema = CollectionSchema(fields=fields, description="RAG document vector store (multi-tenant)")
        self.collection = Collection(name=self.collection_name, schema=schema)

        # Create vector index
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 1024}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)

        # Create default tenant partition
        self._ensure_partition("default")

        logger.info(f"✅ Collection created successfully: {self.collection_name}")
    
    def _ensure_partition(self, tenant_id: str) -> bool:
        """
        Ensure tenant partition exists

        Args:
            tenant_id: Tenant ID

        Returns:
            Success status
        """
        if not self.collection:
            self.collection = Collection(self.collection_name)

        partition_name = self._get_partition_name(tenant_id)

        # Check cache
        if self._tenant_partitions.get(partition_name):
            return True

        try:
            # Check if partition exists
            partitions = self.collection.partitions
            partition_names = [p.name for p in partitions]

            if partition_name not in partition_names:
                # Create partition
                self.collection.create_partition(partition_name)
                logger.info(f"✅ Created tenant partition: {partition_name}")

            # Update cache
            self._tenant_partitions[partition_name] = True
            return True

        except Exception as e:
            logger.error(f"Failed to create partition: {e}")
            return False
    
    def insert(
        self,
        doc_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        tenant_id: str = None
    ):
        """
        Insert document vectors (supports multi-tenancy)

        Args:
            doc_id: Document ID
            chunks: List of document chunks
            embeddings: List of vectors
            tenant_id: Tenant ID
        """
        if not self.collection:
            self.collection = Collection(self.collection_name)

        # Get tenant ID
        tenant_id = self._get_tenant_id(tenant_id)

        # Ensure partition exists
        self._ensure_partition(tenant_id)

        partition_name = self._get_partition_name(tenant_id)

        # Prepare data
        tenant_id = self._get_tenant_id(tenant_id)
        tenant_id_list = [tenant_id] * len(chunks)
        doc_id_list = [doc_id] * len(chunks)
        chunk_index_list = [chunk.get("chunk_index", i) for i, chunk in enumerate(chunks)]
        content_list = [chunk["content"][:5000] for chunk in chunks]
        source_list = [chunk.get("source", "")[:500] for chunk in chunks]
        content_hash_data = [chunk.get("content_hash", "")[:64] for chunk in chunks]

        # Insert data into specified partition
        data = [tenant_id_list, doc_id_list, chunk_index_list, content_list, source_list, content_hash_data, embeddings]
        self.collection.insert(data, partition_name=partition_name)
        self.collection.flush()

        logger.info(f"✅ Inserted {len(chunks)} vectors (tenant: {tenant_id})")
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Dict[str, Any] = None,
        tenant_id: str = None,
        page: int = 1,
        page_size: int = None
    ) -> List[Dict[str, Any]]:
        """
        Vector search (supports multi-tenancy and pagination)

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Additional filter conditions
            tenant_id: Tenant ID
            page: Page number
            page_size: Number of results per page (pagination mode)

        Returns:
            List of search results
        """
        if not self.collection:
            self.collection = Collection(self.collection_name)

        # Get tenant ID
        tenant_id = self._get_tenant_id(tenant_id)
        partition_name = self._get_partition_name(tenant_id)

        # Load collection into memory
        self.collection.load()

        # Vectorize query
        query_embedding = embedding_service.embed_query(query)

        # Search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10}
        }

        # Pagination handling
        if page_size:
            offset = (page - 1) * page_size
            limit = page_size
        else:
            offset = 0
            limit = top_k

        # Build filter expression
        filter_expr = f'tenant_id == "{tenant_id}"'
        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_expr += f' && {key} == "{value}"'
                else:
                    filter_expr += f' && {key} == {value}'

        # Execute search (specify partition)
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            offset=offset,
            expr=filter_expr,
            partition_names=[partition_name],
            output_fields=["doc_id", "chunk_index", "content", "source", "content_hash"]
        )

        # Format results
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "score": hit.score,
                    "doc_id": hit.entity.get("doc_id"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "content": hit.entity.get("content"),
                    "source": hit.entity.get("source"),
                    "content_hash": hit.entity.get("content_hash"),
                    "tenant_id": tenant_id
                })

        return formatted_results
    
    def search_async(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: str = None
    ):
        """
        Async vector search (placeholder, actually needs async embedding)

        Args:
            query: Query text
            top_k: Number of results to return
            tenant_id: Tenant ID

        Note:
            Current implementation is synchronous, can be replaced with true async version later
        """
        # TODO: Use async embedding
        return self.search(query, top_k=top_k, tenant_id=tenant_id)
    
    def delete_by_doc_id(self, doc_id: str, tenant_id: str = None):
        """
        Delete vectors by document ID (supports multi-tenancy)

        Args:
            doc_id: Document ID
            tenant_id: Tenant ID
        """
        if not self.collection:
            self.collection = Collection(self.collection_name)

        tenant_id = self._get_tenant_id(tenant_id)

        expr = f'tenant_id == "{tenant_id}" && doc_id == "{doc_id}"'
        self.collection.delete(expr)
        self.collection.flush()

        logger.info(f"✅ Deleted document vectors: {doc_id} (tenant: {tenant_id})")
    
    def check_duplicate_by_hash(
        self,
        content_hash: str,
        tenant_id: str = None
    ) -> Optional[str]:
        """
        Check if exists by content hash (for deduplication)

        Args:
            content_hash: Content hash
            tenant_id: Tenant ID

        Returns:
            Existing doc_id, None if not exists
        """
        if not self.collection:
            self.collection = Collection(self.collection_name)

        tenant_id = self._get_tenant_id(tenant_id)
        partition_name = self._get_partition_name(tenant_id)

        try:
            self.collection.load()

            # Query if same hash exists
            expr = f'tenant_id == "{tenant_id}" && content_hash == "{content_hash}"'
            results = self.collection.query(
                expr=expr,
                partition_names=[partition_name],
                output_fields=["doc_id"],
                limit=1
            )

            if results:
                return results[0].get("doc_id")
            return None

        except Exception as e:
            logger.error(f"Deduplication check failed: {e}")
            return None
    
    def count(self, tenant_id: str = None) -> int:
        """
        Count vectors (supports multi-tenancy)

        Args:
            tenant_id: Tenant ID
        """
        if not self.collection:
            self.collection = Collection(self.collection_name)

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            partition_name = self._get_partition_name(tenant_id)
            self.collection.load()

            # Query count in tenant partition
            expr = f'tenant_id == "{tenant_id}"'
            results = self.collection.query(
                expr=expr,
                partition_names=[partition_name],
                output_fields=["id"]
            )
            return len(results)
        except Exception as e:
            logger.error(f"Count failed: {e}")
            return 0
    
    def get_tenant_stats(self, tenant_id: str = None) -> Dict[str, Any]:
        """
        Get tenant statistics

        Args:
            tenant_id: Tenant ID

        Returns:
            Statistics
        """
        tenant_id = self._get_tenant_id(tenant_id)

        return {
            "tenant_id": tenant_id,
            "vector_count": self.count(tenant_id),
            "partition_name": self._get_partition_name(tenant_id)
        }


# Singleton
milvus_service = MilvusService()
