# tests/test_main.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "FlavorLens API is running" in response.json()["message"]

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "API is working"

def test_texture_attributes():
    """Test texture attributes endpoint."""
    response = client.get("/api/texture-attributes?ingredient=matcha")
    assert response.status_code == 200
    assert "textureAttributesData" in response.json()
    assert "textureAttributeTrendData" in response.json()

def test_missing_ingredient_parameter():
    """Test endpoint with missing ingredient parameter."""
    response = client.get("/api/texture-attributes")
    assert response.status_code == 422  # Validation error

# tests/test_database.py
import pytest
import asyncio
from database.connection import DatabaseConnection, QueryOptions

@pytest.mark.asyncio
async def test_database_connection():
    """Test database connection."""
    db = DatabaseConnection()
    await db.connect()
    assert db.connection is not None
    await db.close()

@pytest.mark.asyncio
async def test_query_execution():
    """Test query execution."""
    db = DatabaseConnection()
    await db.connect()
    
    # Test simple query
    result = await db.execute_query("SELECT 1 as test_value")
    assert result["rows"]
    assert len(result["rows"]) == 1
    assert result["rows"][0]["test_value"] == 1
    
    await db.close()

@pytest.mark.asyncio
async def test_query_caching():
    """Test query caching functionality."""
    db = DatabaseConnection()
    await db.connect()
    
    # First query - should cache
    options = QueryOptions(cacheable=True, ttl=60000)
    result1 = await db.execute_query("SELECT 1 as test_value", options=options)
    
    # Second query - should use cache
    result2 = await db.execute_query("SELECT 1 as test_value", options=options)
    
    assert result1 == result2
    assert len(db.cache) > 0
    
    await db.close()