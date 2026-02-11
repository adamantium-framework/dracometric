# app/services/vpn_service.py
"""HTTP client management and base VPN service abstraction."""

from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
import logging

from app.models.vpn import VPNServer
from app.settings import settings

logger = logging.getLogger(__name__)

# HTTP client singleton - managed by application lifespan
_http_client: Optional[httpx.AsyncClient] = None


class VPNServiceError(Exception):
    """Base exception for VPN service errors."""

    pass


class VPNAPIError(VPNServiceError):
    """Exception raised when external VPN API calls fail."""

    pass


class VPNDataError(VPNServiceError):
    """Exception raised when VPN data parsing fails."""

    pass


def get_http_client() -> httpx.AsyncClient:
    """Get the shared HTTP client instance."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized. Ensure app lifespan is active.")
    return _http_client


async def create_http_client() -> httpx.AsyncClient:
    """Create HTTP client with optimized settings for high-performance API calls."""
    global _http_client

    _http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,  # Fast fail on connection issues
            read=settings.http_timeout,
            write=10.0,
            pool=5.0,
        ),
        limits=httpx.Limits(
            max_connections=settings.http_max_connections,
            max_keepalive_connections=settings.http_max_keepalive_connections,
            keepalive_expiry=30.0,  # Keep connections alive for 30s
        ),
        http2=True,  # Enable HTTP/2 for better performance
        verify=True,  # Always verify SSL
        follow_redirects=True,
        headers={
            "User-Agent": f"{settings.app_name}/{settings.app_version}",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    logger.info("HTTP client initialized with HTTP/2 and connection pooling")
    return _http_client


async def close_http_client() -> None:
    """Close the HTTP client and release resources."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.info("HTTP client closed")


class AbstractVPNService(ABC):
    """
    Abstract base class for VPN service implementations.

    Defines the contract for fetching VPN server data from providers.
    """

    @abstractmethod
    async def get_servers(self) -> List[VPNServer]:
        """
        Fetch all available VPN servers from the provider.

        Returns:
            List of VPNServer objects in canonical format.

        Raises:
            VPNAPIError: If the external API call fails.
            VPNDataError: If data parsing fails.
        """
        pass

    @abstractmethod
    async def get_servers_by_country(self, country_code: str) -> List[VPNServer]:
        """
        Fetch VPN servers for a specific country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (2 letters).

        Returns:
            List of VPNServer objects for the specified country.

        Raises:
            VPNAPIError: If the external API call fails.
            VPNDataError: If data parsing fails.
        """
        pass
