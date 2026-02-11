"""Pytest configuration and shared fixtures."""

import pytest
import httpx
from aiocache import caches

from app.main import app
from app.services.vpn_service import create_http_client, close_http_client
from app.routers.vpn import _service_instances
from app.settings import settings


# Test API key - use the first configured key or a test key
TEST_API_KEY = settings.api_keys[0] if settings.api_keys else "test-key-for-disabled-auth"

# NordVPN mock URL matching the service URL construction
NORDVPN_MOCK_URL = (
    f"{settings.nordvpn_api_url}"
    f"?filters[servers_technologies][identifier]=wireguard_udp"
    f"&limit={settings.nordvpn_server_limit}"
)


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest.fixture(autouse=True)
async def clear_cache():
    """Clear aiocache between tests to prevent stale cached results."""
    cache = caches.get("default")
    await cache.clear()
    yield
    await cache.clear()


@pytest.fixture
def api_headers():
    """Headers with API key for authenticated requests."""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture
async def test_client(api_headers):
    """Create a test client for the FastAPI app with API key authentication."""
    # Clear service instances to reset cache state
    _service_instances.clear()

    await create_http_client()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=api_headers,
    ) as client:
        yield client
    await close_http_client()

    # Clear service instances after test
    _service_instances.clear()


@pytest.fixture
async def test_client_no_auth():
    """Create a test client WITHOUT API key for testing auth errors."""
    _service_instances.clear()

    await create_http_client()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await close_http_client()

    _service_instances.clear()


@pytest.fixture
def mock_nordvpn_data():
    """Mock data for NordVPN API response."""
    return [
        {
            "hostname": "us1234.nordvpn.com",
            "station": "192.168.1.1",
            "status": "online",
            "load": 25,
            "locations": [{"country": {"name": "United States", "code": "US"}}],
            "technologies": [
                {
                    "identifier": "wireguard_udp",
                    "pivot": {"status": "online"},
                    "metadata": [{"name": "public_key", "value": "test-pubkey-1"}],
                }
            ],
        },
        {
            "hostname": "br5678.nordvpn.com",
            "station": "192.168.1.2",
            "status": "online",
            "load": 50,
            "locations": [{"country": {"name": "Brazil", "code": "BR"}}],
            "technologies": [
                {
                    "identifier": "wireguard_udp",
                    "pivot": {"status": "online"},
                    "metadata": [{"name": "public_key", "value": "test-pubkey-2"}],
                }
            ],
        },
    ]


@pytest.fixture
def mock_nordvpn_data_with_offline():
    """Mock NordVPN data that includes offline servers for filtering tests."""
    return [
        {
            "hostname": "us1234.nordvpn.com",
            "station": "192.168.1.1",
            "status": "online",
            "load": 25,
            "locations": [{"country": {"name": "United States", "code": "US"}}],
            "technologies": [
                {
                    "identifier": "wireguard_udp",
                    "pivot": {"status": "online"},
                    "metadata": [{"name": "public_key", "value": "test-pubkey-1"}],
                }
            ],
        },
        {
            "hostname": "de9999.nordvpn.com",
            "station": "192.168.1.3",
            "status": "offline",
            "load": 0,
            "locations": [{"country": {"name": "Germany", "code": "DE"}}],
            "technologies": [
                {
                    "identifier": "wireguard_udp",
                    "pivot": {"status": "online"},
                    "metadata": [{"name": "public_key", "value": "test-pubkey-offline"}],
                }
            ],
        },
        {
            "hostname": "fr1111.nordvpn.com",
            "station": "192.168.1.4",
            "status": "online",
            "load": 30,
            "locations": [{"country": {"name": "France", "code": "FR"}}],
            "technologies": [
                {
                    "identifier": "wireguard_udp",
                    "pivot": {"status": "offline"},
                    "metadata": [{"name": "public_key", "value": "test-pubkey-wg-offline"}],
                }
            ],
        },
    ]


@pytest.fixture
def mock_surfshark_data():
    """Mock data for Surfshark API response."""
    return [
        {
            "type": "wireguard",
            "connectionName": "us-nyc.prod.surfshark.com",
            "pubKey": "test-surfshark-key-1",
            "country": "United States",
            "countryCode": "US",
            "load": 15,
        },
        {
            "type": "wireguard",
            "connectionName": "br-sao.prod.surfshark.com",
            "pubKey": "test-surfshark-key-2",
            "country": "Brazil",
            "countryCode": "BR",
            "load": 40,
        },
    ]
