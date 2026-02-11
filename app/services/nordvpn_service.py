# app/services/nordvpn_service.py
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


class NordVPNService(AbstractVPNService):
    """
    Service implementation for fetching NordVPN server data.
    """

    @cached(ttl=settings.cache_ttl)
    async def get_servers(self) -> List[VPNServer]:
        """
        Fetches all NordVPN servers that support WireGuard, transforms them
        into the canonical VPNServer model, and caches the result.

        Raises:
            VPNAPIError: If the NordVPN API request fails.
            VPNDataError: If server data parsing fails.
        """
        try:
            # Build URL with WireGuard filter and configurable limit
            nordvpn_url = (
                f"{settings.nordvpn_api_url}"
                f"?filters[servers_technologies][identifier]=wireguard_udp"
                f"&limit={settings.nordvpn_server_limit}"
            )


            logger.info(f"Fetching NordVPN servers from: {nordvpn_url}")

            client = get_http_client()
            response = await client.get(nordvpn_url)
            response.raise_for_status()
            data = response.json()

            logger.info(f"Received {len(data)} servers from NordVPN API")

            servers = self._parse_nordvpn_servers(data)

            # Sort by load for better performance (lowest load first)
            servers.sort(key=lambda s: s.load if s.load is not None else float("inf"))

            logger.info(f"Successfully parsed {len(servers)} NordVPN servers")
            return servers

        except httpx.HTTPStatusError as e:
            logger.error(f"NordVPN API HTTP error: {e.response.status_code} - {e.response.text}")
            raise VPNAPIError(f"NordVPN API request failed: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"NordVPN API request error: {str(e)}")
            raise VPNAPIError(f"Failed to connect to NordVPN API: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching NordVPN servers: {str(e)}")
            raise VPNDataError(f"Failed to process NordVPN server data: {str(e)}") from e

    def _parse_nordvpn_servers(self, data: List[dict]) -> List[VPNServer]:
        """Parse raw NordVPN API data into VPNServer models.

        Filters:
        - Server top-level status must be "online"
        - WireGuard technology pivot.status must be "online"
        - Must have a valid hostname and WireGuard public key
        """
        servers = []
        for server_data in data:
            try:
                # Skip servers that are not online
                if server_data.get("status") != "online":
                    continue

                # Use hostname for DNS-resolvable endpoint (more reliable than static IP)
                hostname = server_data.get("hostname")
                if not hostname:
                    continue

                # Extracting the public key from technologies
                # Also verify WireGuard technology status is online
                pubkey = None
                for tech in server_data.get("technologies", []):
                    if tech.get("identifier") == "wireguard_udp":
                        # Check WireGuard technology is online
                        pivot = tech.get("pivot", {})
                        if pivot.get("status") != "online":
                            break
                        for metadata in tech.get("metadata", []):
                            if metadata.get("name") == "public_key":
                                pubkey = metadata.get("value")
                                break
                        break

                if not pubkey:
                    continue

                country_data = server_data.get("locations", [{}])[0].get("country", {})

                servers.append(
                    VPNServer(
                        provider="nordvpn",
                        country=country_data.get("name", "Unknown"),
                        country_code=country_data.get("code", "XX"),
                        identifier=hostname,
                        public_key=pubkey,
                        load=server_data.get("load"),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to parse NordVPN server: {str(e)}")
                continue

        return servers

    @cached(ttl=settings.cache_ttl, key_builder=lambda f, *args, **kwargs: f"{f.__name__}:{kwargs.get('country_code', args[1] if len(args) > 1 else 'unknown')}")
    async def get_servers_by_country(self, country_code: str) -> List[VPNServer]:
        """
        Returns a list of NordVPN servers for a specific country by fetching
        all servers and filtering them. Results are cached per country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (2 letters).

        Raises:
            VPNAPIError: If the NordVPN API request fails.
            VPNDataError: If server data parsing fails.
        """
        logger.info(f"Fetching NordVPN servers for country: {country_code}")
        all_servers = await self.get_servers()

        filtered = [
            server
            for server in all_servers
            if server.country_code.upper() == country_code.upper()
        ]

        logger.info(f"Found {len(filtered)} NordVPN servers for {country_code}")
        return filtered