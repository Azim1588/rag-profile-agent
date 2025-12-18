# Test Suite Documentation

## Overview

This directory contains the test suite for the RAG Profile Agent application.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_rate_limiter.py
│   ├── test_redis_memory.py
│   ├── test_health_endpoint.py
│   ├── test_config.py
│   ├── test_query_router.py
│   └── test_celery_tasks.py
└── integration/             # Integration tests
    └── test_websocket_chat.py
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Unit Tests Only
```bash
pytest tests/unit/
```

### Run Integration Tests Only
```bash
pytest tests/integration/
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

### Run Specific Test File
```bash
pytest tests/unit/test_rate_limiter.py
```

### Run Specific Test
```bash
pytest tests/unit/test_rate_limiter.py::TestRateLimiter::test_first_message_allowed
```

### Run Tests by Marker
```bash
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m api           # Run only API tests
pytest -m websocket     # Run only WebSocket tests
```

## Test Markers

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.websocket` - WebSocket tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.celery` - Celery task tests

## Coverage Goal

Target coverage: **>70%**

Current coverage can be viewed by running:
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

## Writing New Tests

### Unit Test Example
```python
@pytest.mark.unit
class TestMyService:
    @pytest.fixture
    def my_service(self):
        return MyService()
    
    @pytest.mark.asyncio
    async def test_my_function(self, my_service):
        result = await my_service.my_function()
        assert result == expected_value
```

### Integration Test Example
```python
@pytest.mark.integration
class TestMyEndpoint:
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_my_endpoint(self, client):
        response = client.get("/my-endpoint")
        assert response.status_code == 200
```

## Fixtures

Common fixtures are defined in `conftest.py`:
- `mock_redis_client` - Mock Redis client
- `mock_postgres_session` - Mock PostgreSQL session
- `mock_openai_client` - Mock OpenAI client
- `sample_session_id` - Sample session ID
- `sample_user_id` - Sample user ID
- `test_client` - FastAPI test client
- `async_test_client` - Async test client

## Notes

- All async tests must use `@pytest.mark.asyncio`
- Use mocks for external services (Redis, PostgreSQL, OpenAI)
- Integration tests may require running services (use Docker)
- Set `ENVIRONMENT=test` in environment for test mode

