"""Integration tests for API endpoints."""

import pytest
import respx
import httpx

from app.settings import settings
from tests.conftest import NORDVPN_MOCK_URL


@respx.mock
async def test_health_check(test_client):
    """Test health check endpoint."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@respx.mock
async def test_get_nordvpn_servers(test_client, mock_nordvpn_data):
    """Test getting all NordVPN servers."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["provider"] == "nordvpn"


@respx.mock
async def test_get_nordvpn_servers_with_pagination(test_client, mock_nordvpn_data):
    """Test getting NordVPN servers with pagination."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers?page=1&page_size=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


@respx.mock
async def test_get_nordvpn_servers_paginated_response(test_client, mock_nordvpn_data):
    """Test getting NordVPN servers with paginated response format."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/paginated?page=1&page_size=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total_pages"] == 2
    assert len(data["data"]) == 1


@respx.mock
async def test_get_servers_by_country(test_client, mock_nordvpn_data):
    """Test getting servers by country code."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/US")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_code"] == "US"


@respx.mock
async def test_get_servers_by_country_not_found(test_client, mock_nordvpn_data):
    """Test getting servers for a country with no servers."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/ZZ")
    assert response.status_code == 404


@respx.mock
async def test_get_available_countries(test_client, mock_nordvpn_data):
    """Test getting list of available countries."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/countries")
    assert response.status_code == 200
    data = response.json()
    codes = [c["code"] for c in data]
    assert "US" in codes
    assert "BR" in codes
    assert len(data) == 2


@respx.mock
async def test_invalid_provider(test_client):
    """Test requesting an invalid provider."""
    response = await test_client.get("/api/invalidprovider/servers")
    assert response.status_code == 422  # Validation error for pattern mismatch


@respx.mock
async def test_surfshark_servers(test_client, mock_surfshark_data):
    """Test getting Surfshark servers."""
    respx.get(settings.surfshark_api_url).mock(
        return_value=httpx.Response(200, json=mock_surfshark_data)
    )

    response = await test_client.get("/api/surfshark/servers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["provider"] == "surfshark"


@respx.mock
async def test_surfshark_servers_have_load(test_client, mock_surfshark_data):
    """Test that Surfshark servers include load data."""
    respx.get(settings.surfshark_api_url).mock(
        return_value=httpx.Response(200, json=mock_surfshark_data)
    )

    response = await test_client.get("/api/surfshark/servers")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["load"] == 15
    assert data[1]["load"] == 40


@respx.mock
async def test_api_error_handling(test_client):
    """Test API error handling when external service fails."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    response = await test_client.get("/api/nordvpn/servers")
    assert response.status_code == 503
    assert "error" in response.json()


@respx.mock
async def test_security_headers(test_client, mock_nordvpn_data):
    """Test that security headers are present."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers")
    assert response.status_code == 200

    if settings.enable_security_headers:
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers


@respx.mock
async def test_rate_limit_headers(test_client, mock_nordvpn_data):
    """Test that rate limit headers are present."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers")
    assert response.status_code == 200

    if settings.rate_limit_enabled:
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers


@respx.mock
async def test_top_servers(test_client, mock_nordvpn_data):
    """Test top servers endpoint returns servers sorted by performance."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/top?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Sorted by load (lowest first): US=25, BR=50
    assert data[0]["load"] <= data[1]["load"]


@respx.mock
async def test_top_servers_with_country_filter(test_client, mock_nordvpn_data):
    """Test top servers endpoint with country filter."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/top?limit=5&country_code=US")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_code"] == "US"


@respx.mock
async def test_top_servers_country_not_found(test_client, mock_nordvpn_data):
    """Test top servers endpoint with nonexistent country."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/top?country_code=ZZ")
    assert response.status_code == 404


@respx.mock
async def test_paginated_page_out_of_range(test_client, mock_nordvpn_data):
    """Test paginated endpoint returns 404 for out-of-range page."""
    respx.get(NORDVPN_MOCK_URL).mock(return_value=httpx.Response(200, json=mock_nordvpn_data))

    response = await test_client.get("/api/nordvpn/servers/paginated?page=999&page_size=100")
    assert response.status_code == 404
