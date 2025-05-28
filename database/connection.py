# database/connection.py (Optimized for MotherDuck)
import duckdb
from typing import Dict, List, Any
from dataclasses import dataclass
import hashlib
import time
import logging
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryOptions:
    cacheable: bool = False
    ttl: int = settings.default_cache_ttl

class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        
    async def connect(self):
        """Initialize MotherDuck database connection"""
        if self._initialized and self.connection:
            return
            
        try:
            motherduck_token = settings.motherduck_token
            if not motherduck_token:
                raise ValueError("MOTHERDUCK_TOKEN is required")
                
            connection_string = f"{settings.database_url}?motherduck_token={motherduck_token}"
            logger.info("🦆 Connecting to MotherDuck...")
            
            # Track connection time
            start_time = time.time()
            self.connection = duckdb.connect(connection_string)
            connection_time = time.time() - start_time
            
            # MotherDuck optimizations
            try:
                self.connection.execute("SET enable_http_metadata_cache=true")
                self.connection.execute("SET http_timeout=30000")
                self.connection.execute("SET http_keep_alive=true")
                self.connection.execute("SET http_retries=3")
            except Exception as opt_error:
                logger.warning(f"⚠️ Some optimizations failed: {opt_error}")
            
            self._initialized = True
            logger.info(f"✅ MotherDuck connected successfully in {connection_time:.2f}s!")
                
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self.connection = None
            self._initialized = False
            raise e
    
    def _generate_cache_key(self, query: str, params: List[Any]) -> str:
        """Generate cache key from query and parameters"""
        content = f"{query}:{str(params)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any], ttl: int) -> bool:
        """Check if cache entry is still valid"""
        current_time = int(time.time() * 1000)
        return (current_time - cache_entry["timestamp"]) < ttl
    
    async def execute_query(
        self, 
        query: str, 
        params: List[Any] = None, 
        options: QueryOptions = None
    ) -> Dict[str, Any]:
        """Execute a query with optional caching"""
        if params is None:
            params = []
        if options is None:
            options = QueryOptions()
            
        # Check cache first
        if settings.enable_caching and options.cacheable:
            cache_key = self._generate_cache_key(query, params)
            if cache_key in self.cache:
                cache_entry = self.cache[cache_key]
                if self._is_cache_valid(cache_entry, options.ttl):
                    return cache_entry["data"]
                else:
                    del self.cache[cache_key]
        
        try:
            # Ensure connection
            if not self._initialized:
                await self.connect()
                
            # Execute query
            if params:
                result = self.connection.execute(query, params)
            else:
                result = self.connection.execute(query)
                
            # Fetch and format results
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description] if result.description else []
            
            formatted_rows = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(columns):
                        row_dict[columns[i]] = value
                formatted_rows.append(row_dict)
            
            query_result = {
                "rows": formatted_rows,
                "columns": columns,
                "row_count": len(formatted_rows)
            }
            
            # Cache result if enabled
            if settings.enable_caching and options.cacheable:
                cache_key = self._generate_cache_key(query, params)
                self.cache[cache_key] = {
                    "data": query_result,
                    "timestamp": int(time.time() * 1000)
                }
            
            return query_result
            
        except Exception as e:
            logger.error(f"❌ Query error: {e}")
            # Reset connection on connection errors
            if "connection" in str(e).lower():
                self._initialized = False
                self.connection = None
            raise e
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self._initialized = False

# Global database instance
db_instance = DatabaseConnection()

async def get_db_connection():
    """Get database connection instance"""
    if not db_instance._initialized:
        await db_instance.connect()
    return db_instance

async def execute_query(
    query: str, 
    params: List[Any] = None, 
    options: QueryOptions = None
) -> Dict[str, Any]:
    """Execute a database query"""
    db = await get_db_connection()
    return await db.execute_query(query, params, options)

async def close_db_connection():
    """Close database connection"""
    await db_instance.close()