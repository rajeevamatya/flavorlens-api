# database/connection.py (Updated to use config.py settings)
import duckdb
from typing import Dict, List, Any
from dataclasses import dataclass
import hashlib
import time
import logging

# Import settings from config.py
from config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryOptions:
    cacheable: bool = False
    ttl: int = settings.default_cache_ttl  # Use from config

class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.connection_info = {}
        
    async def connect(self):
        """Initialize MotherDuck database connection"""
        try:
            # Get MotherDuck token from settings
            motherduck_token = settings.motherduck_token
            
            if not motherduck_token:
                raise ValueError("MOTHERDUCK_TOKEN is required but not found in settings")
                
            # Connect to MotherDuck using database_url from settings
            connection_string = f"{settings.database_url}?motherduck_token={motherduck_token}"
            logger.info("🦆 Connecting to MotherDuck...")
            self.connection = duckdb.connect(connection_string)
            
            # Verify connection
            result = self.connection.execute("SELECT 1 as test").fetchone()
            if result[0] != 1:
                raise Exception("MotherDuck connection test failed")
                
            # Get version info
            version_result = self.connection.execute("SELECT version()").fetchone()
            logger.info(f"📊 DuckDB Version: {version_result[0]}")
            
            # Check for tables
            tables_result = self.connection.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'main'
                LIMIT 5
            """).fetchall()
            
            table_names = [row[0] for row in tables_result] if tables_result else []
            
            self.connection_info = {
                "type": "motherduck",
                "database": settings.database_url.split(":")[-1],
                "tables": table_names
            }
            
            logger.info("✅ Successfully connected to MotherDuck!")
                
        except Exception as e:
            logger.error(f"❌ MotherDuck connection error: {e}")
            raise e
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get information about the current database connection"""
        return self.connection_info
    
    def _generate_cache_key(self, query: str, params: List[Any]) -> str:
        """Generate cache key from query and parameters"""
        content = f"{query}:{str(params)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any], ttl: int) -> bool:
        """Check if cache entry is still valid"""
        current_time = int(time.time() * 1000)  # Current time in milliseconds
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
            
        # Check if caching is enabled globally and for this query
        if settings.enable_caching and options.cacheable:
            cache_key = self._generate_cache_key(query, params)
            if cache_key in self.cache:
                cache_entry = self.cache[cache_key]
                if self._is_cache_valid(cache_entry, options.ttl):
                    logger.info("📦 Using cached query result")
                    return cache_entry["data"]
                else:
                    # Remove expired cache entry
                    del self.cache[cache_key]
        
        try:
            if not self.connection:
                await self.connect()
                
            start_time = time.time()
            
            # Execute query
            if params:
                result = self.connection.execute(query, params)
            else:
                result = self.connection.execute(query)
                
            # Fetch results
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description] if result.description else []
            
            execution_time = time.time() - start_time
            
            # Convert to list of dictionaries
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
                "row_count": len(formatted_rows),
                "execution_time": execution_time,
                "connection_type": "motherduck"
            }
            
            # Log query performance
            logger.info(f"⚡ Query executed in {execution_time:.3f}s, returned {len(formatted_rows)} rows")
            
            # Cache result if enabled globally and for this query
            if settings.enable_caching and options.cacheable:
                cache_key = self._generate_cache_key(query, params)
                self.cache[cache_key] = {
                    "data": query_result,
                    "timestamp": int(time.time() * 1000)
                }
            
            return query_result
            
        except Exception as e:
            logger.error(f"❌ Query execution error: {e}")
            logger.error(f"Query: {query[:100]}...")
            logger.error(f"Params: {params}")
            raise e
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("🔌 Database connection closed")

# Global database instance
db_instance = DatabaseConnection()

async def get_db_connection():
    """Get database connection instance"""
    if not db_instance.connection:
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

async def get_connection_info() -> Dict[str, Any]:
    """Get information about the current database connection"""
    db = await get_db_connection()
    return db.get_connection_info()

async def close_db_connection():
    """Close database connection"""
    await db_instance.close()

async def test_motherduck_connection():
    """Test MotherDuck connection and return info"""
    try:
        db = await get_db_connection()
        test_result = await execute_query("SELECT 'MotherDuck connection test' as message, current_timestamp as timestamp")
        return {
            "status": "success",
            "test_query": test_result,
            "connection_info": db.get_connection_info(),
            "settings": {
                "database_url": settings.database_url,
                "motherduck_token": "***" if settings.motherduck_token else None,
                "enable_caching": settings.enable_caching,
                "default_cache_ttl": settings.default_cache_ttl
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "settings": {
                "database_url": settings.database_url,
                "motherduck_token_exists": settings.motherduck_token is not None,
                "enable_caching": settings.enable_caching
            }
        }