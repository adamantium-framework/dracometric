# app/services/surfshark_service.py
from typing import List
import logging
import httpx
from aiocache import cached
from app.models.vpn import VPNServer
from app.services.vpn_service import (
    AbstractVPNService,
    get_http_client,
    VPNAPIError,
    VPNDataError,
)
from app.settings import settings

logger = logging.getLogger(__name__)


class SurfsharkService(AbstractVPNService):
    """
    Service implementation for fetching Surfshark server data.
    """

    @cached(ttl=settings.cache_ttl)
    async def get_servers(self) -> List[VPNServer]:
        """
        Fetches all Surfshark servers, transforms them into the canonical
        VPNServer model, and caches the result.

        Raises:
            VPNAPIError: If the Surfshark API request fails.
            VPNDataError: If server data parsing fails.
        """
        try:
            logger.info(f"Fetching Surfshark servers from: {settings.surfshark_api_url}")

            client = get_http_client()
            response = await client.get(settings.surfshark_api_url)
            response.raise_for_status()
            data = response.json()

            logger.info(f"Received {len(data)} servers from Surfshark API")

            servers = self._parse_surfshark_servers(data)

            logger.info(f"Successfully parsed {len(servers)} Surfshark servers")
            return servers

        except httpx.HTTPStatusError as e:
            logger.error(f"Surfshark API HTTP error: {e.response.status_code} - {e.response.text}")
            raise VPNAPIError(f"Surfshark API request failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"Surfshark API request error: {str(e)}")
            raise VPNAPIError(f"Failed to connect to Surfshark API: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching Surfshark servers: {str(e)}")
            raise VPNDataError(f"Failed to process Surfshark server data: {str(e)}") from e

    def _parse_surfshark_servers(self, data: List[dict]) -> List[VPNServer]:
        """Parse raw Surfshark API data into VPNServer models.

        Note: Surfshark API has no explicit "status" field. All servers
        returned by the API are considered online (offline servers are
        not included in the response). The API does provide a "load"
        field which is captured for performance ranking.
        """
        servers = []
        for server_data in data:
            try:
                connection_name = server_data.get("connectionName")
                if not connection_name:
                    continue

                # Filter for WireGuard or generic types with a public key
                if (
                    server_data.get("type") in ["wireguard", "generic"]
                    and server_data.get("pubKey")
                ):
                    servers.append(
                        VPNServer(
                            provider="surfshark",
                            country=server_data.get("country", "Unknown"),
                            country_code=server_data.get("countryCode", "XX"),
                            identifier=connection_name,
                            public_key=server_data.get("pubKey"),
                            load=server_data.get("load"),
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to parse Surfshark server: {str(e)}")
                continue

        return servers

    @cached(ttl=settings.cache_ttl, key_builder=lambda f, *args, **kwargs: f"{f.__name__}:{kwargs.get('country_code', args[1] if len(args) > 1 else 'unknown')}")
    async def get_servers_by_country(self, country_code: str) -> List[VPNServer]:
        """
        Returns a list of Surfshark servers for a specific country by fetching
        all servers and filtering them. Results are cached per country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (2 letters).

        Raises:
            VPNAPIError: If the Surfshark API request fails.
            VPNDataError: If server data parsing fails.
        """
        logger.info(f"Fetching Surfshark servers for country: {country_code}")
        all_servers = await self.get_servers()

        filtered = [
            server
            for server in all_servers
            if server.country_code.upper() == country_code.upper()
        ]

        logger.info(f"Found {len(filtered)} Surfshark servers for {country_code}")
        return filtered