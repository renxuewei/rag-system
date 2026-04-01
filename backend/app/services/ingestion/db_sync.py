"""
Database synchronization service
Supports data sync from PostgreSQL, MySQL and other databases
"""

from typing import Dict, Any, Optional, List, Generator
import logging
from datetime import datetime

from .base import BaseIngestion, IngestionResult

logger = logging.getLogger(__name__)


class DatabaseSync(BaseIngestion):
    """Database synchronization service"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

        self.batch_size = self.config.get("batch_size", 1000)

        # Database connection cache
        self._connections: Dict[str, Any] = {}

        # Sync status
        self._sync_states: Dict[str, Dict[str, Any]] = {}

    def register_database(
        self,
        name: str,
        connection_string: str,
        db_type: str = "postgresql"
    ):
        """
        Register database

        Args:
            name: Database alias
            connection_string: Connection string
            db_type: Database type
        """
        self._connections[name] = {
            "connection_string": connection_string,
            "db_type": db_type,
            "engine": None
        }

        logger.info(f"Registered database: {name} ({db_type})")

    def ingest(
        self,
        source: str,
        query: str = None,
        table: str = None,
        columns: List[str] = None,
        where: str = None,
        incremental_field: str = None,
        last_sync_time: datetime = None,
        **kwargs
    ) -> IngestionResult:
        """
        Sync data from database

        Args:
            source: Database alias:table_name or custom query
            query: SQL query
            table: Table name
            columns: Column name list
            where: WHERE condition
            incremental_field: Incremental sync field
            last_sync_time: Last sync time
        """
        db_name, table_name = self._parse_source(source, table)
        
        if db_name not in self._connections:
            return IngestionResult(
                source=source,
                content="",
                success=False,
                error=f"Unregistered database: {db_name}"
            )

        try:
            # Get database connection
            engine = self._get_engine(db_name)

            # Build query
            if query:
                sql = query
            else:
                sql = self._build_query(
                    table=table_name,
                    columns=columns,
                    where=where,
                    incremental_field=incremental_field,
                    last_sync_time=last_sync_time
                )

            # Execute query
            import pandas as pd
            df = pd.read_sql(sql, engine)

            # Convert to text
            content = self._dataframe_to_text(df, table_name)
            
            metadata = {
                "database": db_name,
                "table": table_name,
                "row_count": len(df),
                "columns": list(df.columns),
                "sync_time": datetime.utcnow().isoformat()
            }

            # Update sync status
            self._update_sync_state(db_name, table_name, len(df))

            return IngestionResult(
                source=source,
                content=content,
                metadata=metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"Database sync failed: {source} - {e}")
            return IngestionResult(
                source=source,
                content="",
                success=False,
                error=str(e)
            )
    
    async def ingest_async(
        self, 
        source: str,
        query: str = None,
        table: str = None,
        columns: List[str] = None,
        where: str = None,
        **kwargs
    ) -> IngestionResult:
        """Async database sync"""
        # Database operations are blocking, use run_in_executor here
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: self.ingest(
                    source, query, table, columns, where, **kwargs
                )
            )

        return result
    
    def sync_incremental(
        self,
        source: str,
        incremental_field: str = "updated_at",
        batch_size: int = None
    ) -> List[IngestionResult]:
        """
        Incremental sync

        Args:
            source: Data source
            incremental_field: Incremental field
            batch_size: Batch size
        """
        db_name, table_name = self._parse_source(source)

        # Get last sync time
        last_sync = self._sync_states.get(f"{db_name}:{table_name}", {}).get("last_sync_time")

        results = []
        offset = 0
        batch_size = batch_size or self.batch_size
        
        while True:
            result = self.ingest(
                source,
                incremental_field=incremental_field,
                last_sync_time=last_sync
            )
            
            if not result.success:
                break
            
            row_count = result.metadata.get("row_count", 0)
            if row_count == 0:
                break
            
            results.append(result)
            
            if row_count < batch_size:
                break
            
            offset += batch_size
        
        return results
    
    def stream_data(
        self,
        source: str,
        query: str = None,
        chunk_size: int = 100
    ) -> Generator[IngestionResult, None, None]:
        """
        Stream data retrieval

        Args:
            source: Data source
            query: SQL query
            chunk_size: Chunk size
        """
        db_name, table_name = self._parse_source(source)

        if db_name not in self._connections:
            yield IngestionResult(
                source=source,
                content="",
                success=False,
                error=f"Unregistered database: {db_name}"
            )
            return
        
        try:
            engine = self._get_engine(db_name)
            
            if query:
                sql = query
            else:
                sql = f"SELECT * FROM {table_name}"
            
            import pandas as pd
            
            for chunk_df in pd.read_sql(sql, engine, chunksize=chunk_size):
                content = self._dataframe_to_text(chunk_df, table_name)
                
                yield IngestionResult(
                    source=source,
                    content=content,
                    metadata={
                        "database": db_name,
                        "table": table_name,
                        "row_count": len(chunk_df)
                    },
                    success=True
                )

        except Exception as e:
            logger.error(f"Streaming sync failed: {source} - {e}")
            yield IngestionResult(
                source=source,
                content="",
                success=False,
                error=str(e)
            )
    
    def _parse_source(self, source: str, table: str = None) -> tuple:
        """Parse data source"""
        if table:
            return source, table

        if ":" in source:
            db_name, table_name = source.split(":", 1)
            return db_name, table_name

        return source, ""

    def _get_engine(self, db_name: str):
        """Get database engine"""
        config = self._connections[db_name]
        
        if config["engine"] is None:
            from sqlalchemy import create_engine
            config["engine"] = create_engine(config["connection_string"])
        
        return config["engine"]
    
    def _build_query(
        self,
        table: str,
        columns: List[str] = None,
        where: str = None,
        incremental_field: str = None,
        last_sync_time: datetime = None
    ) -> str:
        """Build SQL query"""
        if columns:
            select = ", ".join(columns)
        else:
            select = "*"

        sql = f"SELECT {select} FROM {table}"

        conditions = []

        if where:
            conditions.append(where)

        if incremental_field and last_sync_time:
            conditions.append(f"{incremental_field} > '{last_sync_time.isoformat()}'")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return sql
    
    def _dataframe_to_text(self, df, table_name: str) -> str:
        """Convert DataFrame to text"""
        import json

        # Convert each row to text
        records = df.to_dict(orient="records")

        text_parts = []
        for i, record in enumerate(records):
            # Build descriptive text
            parts = [f"[{table_name} record {i+1}]"]

            for key, value in record.items():
                if value is not None:
                    parts.append(f"{key}: {value}")

            text_parts.append("\n".join(parts))

        return "\n\n".join(text_parts)
    
    def _update_sync_state(self, db_name: str, table_name: str, row_count: int):
        """Update sync status"""
        key = f"{db_name}:{table_name}"

        if key not in self._sync_states:
            self._sync_states[key] = {
                "total_synced": 0,
                "sync_count": 0
            }

        self._sync_states[key]["total_synced"] += row_count
        self._sync_states[key]["sync_count"] += 1
        self._sync_states[key]["last_sync_time"] = datetime.utcnow()

    def get_sync_state(self, source: str) -> Dict[str, Any]:
        """Get sync status"""
        db_name, table_name = self._parse_source(source)
        key = f"{db_name}:{table_name}"
        return self._sync_states.get(key, {})


# Singleton
db_sync = DatabaseSync()
