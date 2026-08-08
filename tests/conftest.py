import asyncio
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.embedder import TextEmbedder


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for session-scoped async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def init_embedder():
    """Ensure TextEmbedder singleton is initialized for test execution."""
    return TextEmbedder.get_instance()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client fixture wrapping the FastAPI application.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
