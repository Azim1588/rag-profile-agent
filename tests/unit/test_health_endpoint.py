"""Unit tests for health check endpoints."""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.unit
@pytest.mark.api
class TestHealthEndpoints:
    """Test cases for health check endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "RAG Profile Agent API" in data["message"]
        assert "docs" in data
        assert "health" in data
    
    def test_health_check(self, client):
        """Test basic health check."""
        response = client.get("/v1/health/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_liveness_check(self, client):
        """Test liveness check."""
        response = client.get("/v1/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
    
    def test_readiness_check(self, client):
        """Test readiness check."""
        response = client.get("/v1/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data

