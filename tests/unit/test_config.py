"""Unit tests for configuration."""
import pytest
import os
from app.core.config import settings


@pytest.mark.unit
class TestSettings:
    """Test cases for application settings."""
    
    def test_settings_loaded(self):
        """Test that settings are loaded."""
        assert settings.APP_NAME == "rag-profile-agent"
        assert settings.API_VERSION == "v1"
    
    def test_database_url_construction(self):
        """Test database URL construction."""
        url = settings.get_database_url()
        assert "postgresql" in url
        assert "asyncpg" in url or "@" in url
    
    def test_redis_url_construction(self):
        """Test Redis URL construction."""
        url = settings.get_redis_url()
        assert "redis://" in url
    
    def test_openai_model_defaults(self):
        """Test OpenAI model defaults."""
        assert settings.OPENAI_MODEL == "gpt-4o-mini"
        assert settings.OPENAI_EMBEDDING_MODEL == "text-embedding-3-small"
    
    def test_rate_limit_settings(self):
        """Test rate limiting settings."""
        # Check that settings have reasonable defaults
        assert hasattr(settings, 'TOP_K_RESULTS')
        assert hasattr(settings, 'SIMILARITY_THRESHOLD')

