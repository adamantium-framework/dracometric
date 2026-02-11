# app/routers/vpn.py
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from app.models.vpn import VPNServer, CountryInfo
from app.services.vpn_service import AbstractVPNService
from app.services.nordvpn_service import NordVPNService
from app.services.surfshark_service import SurfsharkService
from app.services.latency_service import get_latency_service, LatencyService
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["VPN Servers"],
    responses={404: {"description": "Not found"}},
)


# Response models
class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[VPNServer]


class LatencyMeasurementResponse(BaseModel):
    """Response for latency measurement endpoint."""

    total_servers: int
    measured: int
    successful: int
    failed: int
    method: str
    servers: List[VPNServer]


# --- Dependency Factory ---

# Singleton instances of services
_service_instances: Dict[str, AbstractVPNService] = {}


def get_vpn_service_instance(provider: str) -> AbstractVPNService:
    """Get or create singleton service instance."""
    if provider not in _service_instances:
        if provider == "nordvpn":
            _service_instances[provider] = NordVPNService()
        elif provider == "surfshark":
            _service_instances[provider] = SurfsharkService()
        else:
            raise ValueError(f"Unknown provider: {provider}")
    return _service_instances[provider]


def get_vpn_service(
    provider: str = Path(
        ...,
        description="The VPN provider to use",
        pattern="^(nordvpn|surfshark)$",
    )
) -> AbstractVPNService:
    """
    Dependency to get the appropriate VPN service based on the provider path parameter.

    Args:
        provider: The VPN provider name (nordvpn or surfshark).

    Returns:
        AbstractVPNService: The service instance for the specified provider.

    Raises:
        HTTPException: If provider is not found.
    """
    try:
        return get_vpn_service_instance(provider.lower())
    except ValueError:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not supported."
        )


# --- API Endpoints ---
# IMPORTANT: Specific routes must come BEFORE parameterized routes like {country_code}


@router.get(
    "/{provider}/servers",
    response_model=List[VPNServer],
    summary="Get all VPN servers for a provider",
    description="Retrieves all available VPN servers for a specified provider with optional pagination.",
)
async def get_all_servers_for_provider(
    service: AbstractVPNService = Depends(get_vpn_service),
    page: int = Query(
        1, ge=1, description="Page number (1-indexed) for pagination"
    ),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Number of results per page (max: {settings.max_page_size})",
    ),
):
    """
    Retrieves all available VPN servers for a specified provider.

    - **nordvpn**: Servers are sorted by load (lowest first).
    - **surfshark**: Servers are returned in API order (load data not available).

    Use pagination parameters to control response size for better performance.
    """
    logger.info(f"Fetching servers for {service.__class__.__name__} (page={page}, page_size={page_size})")

    servers = await service.get_servers()

    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_servers = servers[start_idx:end_idx]

    logger.info(
        f"Returning {len(paginated_servers)} of {len(servers)} servers "
        f"(page {page}, page_size {page_size})"
    )

    return paginated_servers


@router.get(
    "/{provider}/servers/paginated",
    response_model=PaginatedResponse,
    summary="Get all VPN servers with pagination metadata",
    description="Retrieves all available VPN servers with full pagination metadata.",
)
async def get_all_servers_paginated(
    service: AbstractVPNService = Depends(get_vpn_service),
    page: int = Query(
        1, ge=1, description="Page number (1-indexed) for pagination"
    ),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Number of results per page (max: {settings.max_page_size})",
    ),
):
    """
    Retrieves all available VPN servers with pagination metadata.

    Returns a structured response with:
    - Total number of servers
    - Current page and page size
    - Total number of pages
    - Server data for the current page
    """
    servers = await service.get_servers()
    total = len(servers)
    total_pages = (total + page_size - 1) // page_size

    # Validate page number
    if page > total_pages and total > 0:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} does not exist. Total pages: {total_pages}",
        )

    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_servers = servers[start_idx:end_idx]

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=paginated_servers,
    )


@router.get(
    "/{provider}/servers/top",
    response_model=List[VPNServer],
    summary="Get top best-performing servers",
    description="Retrieves the top servers with the lowest latency/load for optimal performance.",
)
async def get_top_servers(
    service: AbstractVPNService = Depends(get_vpn_service),
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Number of top servers to return (default: 10, max: 50)",
    ),
    country_code: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Optional: Filter by ISO 3166-1 alpha-2 country code",
    ),
):
    """
    Retrieves the top servers with the best performance metrics.

    Servers are ranked by:
    1. **Latency** (if available) - lower is better
    2. **Load** (fallback) - lower is better

    For NordVPN, servers are sorted by load percentage.
    For Surfshark, servers are returned in API order (no load data available).

    Use the optional `country_code` parameter to filter results by country.
    """
    logger.info(
        f"Fetching top {limit} servers for {service.__class__.__name__}"
        f"{f' in {country_code}' if country_code else ''}"
    )

    # Get servers (optionally filtered by country)
    if country_code:
        servers = await service.get_servers_by_country(country_code.upper())
        if not servers:
            provider_name = service.__class__.__name__.replace("Service", "").lower()
            raise HTTPException(
                status_code=404,
                detail=f"No servers found for country '{country_code}' with provider '{provider_name}'.",
            )
    else:
        servers = await service.get_servers()

    # Sort by latency first (if available), then by load
    def performance_key(server: VPNServer) -> tuple:
        latency = server.latency if server.latency is not None else float("inf")
        load = server.load if server.load is not None else float("inf")
        return (latency, load)

    sorted_servers = sorted(servers, key=performance_key)
    top_servers = sorted_servers[:limit]

    logger.info(f"Returning top {len(top_servers)} servers")

    return top_servers


@router.get(
    "/{provider}/servers/latency",
    response_model=LatencyMeasurementResponse,
    summary="Measure server latency",
    description="Measures actual network latency to VPN servers using ping or TCP connect.",
)
async def measure_server_latency(
    service: AbstractVPNService = Depends(get_vpn_service),
    latency_service: LatencyService = Depends(get_latency_service),
    country_code: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Optional: Filter by ISO 3166-1 alpha-2 country code",
    ),
    limit: int = Query(
        0,
        ge=0,
        le=5000,
        description="Maximum number of servers to measure (0 = ALL, default: 0)",
    ),
    method: str = Query(
        "auto",
        pattern="^(auto|fping|tcp)$",
        description="Measurement method: auto (fping if available, else tcp), fping, or tcp",
    ),
):
    """
    Measures actual network latency to VPN servers.

    **Methods:**
    - `auto`: Uses fping if available (fastest), falls back to TCP
    - `fping`: Uses fping command (requires fping installed, may need root)
    - `tcp`: TCP connect latency (no root required, works everywhere)

    **Notes:**
    - fping is significantly faster for bulk measurements
    - TCP measures connection establishment time to WireGuard port (51820)
    - Results are sorted by latency (lowest first)

    **Performance:**
    - fping: ~2-5 seconds for 100 servers
    - tcp: ~10-30 seconds for 100 servers (parallelized)
    """
    logger.info(
        f"Measuring latency for {service.__class__.__name__} "
        f"(country={country_code}, limit={limit}, method={method})"
    )

    # Get servers
    if country_code:
        servers = await service.get_servers_by_country(country_code.upper())
        if not servers:
            provider_name = service.__class__.__name__.replace("Service", "").lower()
            raise HTTPException(
                status_code=404,
                detail=f"No servers found for country '{country_code}' with provider '{provider_name}'.",
            )
    else:
        servers = await service.get_servers()

    # Limit servers to measure (0 = all)
    if limit == 0:
        servers_to_measure = servers
    else:
        servers_to_measure = servers[:limit]
    total = len(servers_to_measure)

    # Measure latency
    measured_servers = await latency_service.measure_servers_latency(
        servers_to_measure,
        method=method,
    )

    # Sort by latency (lowest first)
    def latency_key(server: VPNServer) -> float:
        return server.latency if server.latency is not None else float("inf")

    sorted_servers = sorted(measured_servers, key=latency_key)

    # Count results
    successful = sum(1 for s in sorted_servers if s.latency is not None)
    failed = total - successful

    # Determine actual method used
    actual_method = "fping" if latency_service.fping_available and method in ("auto", "fping") else "tcp"

    logger.info(
        f"Latency measurement complete: {successful}/{total} successful, "
        f"method={actual_method}"
    )

    return LatencyMeasurementResponse(
        total_servers=total,
        measured=total,
        successful=successful,
        failed=failed,
        method=actual_method,
        servers=sorted_servers,
    )


@router.get(
    "/{provider}/servers/fastest",
    response_model=List[VPNServer],
    summary="Get fastest servers by measured latency",
    description="Measures latency and returns the fastest servers.",
)
async def get_fastest_servers(
    service: AbstractVPNService = Depends(get_vpn_service),
    latency_service: LatencyService = Depends(get_latency_service),
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Number of fastest servers to return (default: 10)",
    ),
    country_code: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        pattern="^[A-Z]{2}$",
        description="Optional: Filter by country code",
    ),
    measure_count: int = Query(
        0,
        ge=0,
        le=5000,
        description="Number of servers to measure (0 = ALL servers, default: 0)",
    ),
    exclude: Optional[str] = Query(
        None,
        description="Exclude countries (hyphen-separated codes, e.g., 'BR-US-DE')",
    ),
):
    """
    Measures actual latency to servers and returns the fastest ones.

    This endpoint:
    1. Gets servers (optionally filtered by country)
    2. Excludes specified countries if provided
    3. Measures latency to servers (all by default, or limited by `measure_count`)
    4. Returns the `limit` fastest servers

    **Parameters:**
    - `limit`: Number of fastest servers to return (default: 10)
    - `measure_count`: How many servers to measure (0 = ALL, default: 0)
    - `country_code`: Optional filter by country (include only this country)
    - `exclude`: Exclude countries (e.g., 'BR-US' excludes Brazil and US)

    **Use cases:**
    - Find the best server for your location
    - Get low-latency servers for gaming/streaming
    - Select optimal servers for performance-critical applications
    - Exclude nearby countries to find alternatives
    """
    # Get servers
    if country_code:
        servers = await service.get_servers_by_country(country_code.upper())
        if not servers:
            provider_name = service.__class__.__name__.replace("Service", "").lower()
            raise HTTPException(
                status_code=404,
                detail=f"No servers found for country '{country_code}' with provider '{provider_name}'.",
            )
    else:
        servers = await service.get_servers()

    # Exclude countries if specified
    if exclude:
        excluded_codes = {code.strip().upper() for code in exclude.split("-") if code.strip()}
        servers = [s for s in servers if s.country_code not in excluded_codes]
        if not servers:
            raise HTTPException(
                status_code=404,
                detail=f"No servers found after excluding countries: {', '.join(sorted(excluded_codes))}",
            )

    # Determine how many to measure (0 = all)
    actual_measure_count = len(servers) if measure_count == 0 else min(measure_count, len(servers))

    logger.info(
        f"Finding {limit} fastest servers for {service.__class__.__name__} "
        f"(country={country_code}, measuring={actual_measure_count}/{len(servers)})"
    )

    # Sort by load first (measure low-load servers first for efficiency)
    def load_key(s: VPNServer) -> int:
        return s.load if s.load is not None else 50

    sorted_by_load = sorted(servers, key=load_key)
    servers_to_measure = sorted_by_load[:actual_measure_count]

    # Measure latency
    measured_servers = await latency_service.measure_servers_latency(
        servers_to_measure,
        method="auto",
    )

    # Filter only successful measurements and sort by latency
    reachable_servers = [s for s in measured_servers if s.latency is not None]

    if not reachable_servers:
        raise HTTPException(
            status_code=503,
            detail="Could not reach any servers. Check network connectivity.",
        )

    fastest_servers = sorted(reachable_servers, key=lambda s: s.latency)[:limit]

    logger.info(
        f"Found {len(fastest_servers)} fastest servers "
        f"(best latency: {fastest_servers[0].latency:.1f}ms)"
    )

    return fastest_servers


# NOTE: This route MUST come AFTER specific /servers/* routes above
@router.get(
    "/{provider}/servers/{country_code}",
    response_model=List[VPNServer],
    summary="Get VPN servers by country",
    description="Retrieves available VPN servers for a specific country with optional pagination.",
)
async def get_servers_by_country(
    country_code: str = Path(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'BR')",
        pattern="^[A-Z]{2}$",
    ),
    service: AbstractVPNService = Depends(get_vpn_service),
    page: int = Query(
        1, ge=1, description="Page number (1-indexed) for pagination"
    ),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Number of results per page (max: {settings.max_page_size})",
    ),
):
    """
    Retrieves available VPN servers for a specific country and provider.

    - **nordvpn**: Servers are sorted by load (lowest first).
    - **surfshark**: Servers are returned in API order.

    Country code must be a valid ISO 3166-1 alpha-2 code (2 uppercase letters).
    """
    logger.info(
        f"Fetching servers for {country_code} from {service.__class__.__name__}"
    )

    servers = await service.get_servers_by_country(country_code.upper())

    if not servers:
        provider_name = service.__class__.__name__.replace("Service", "").lower()
        raise HTTPException(
            status_code=404,
            detail=f"No servers found for country '{country_code}' with provider '{provider_name}'.",
        )

    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_servers = servers[start_idx:end_idx]

    logger.info(
        f"Returning {len(paginated_servers)} of {len(servers)} servers for {country_code}"
    )

    return paginated_servers


@router.get(
    "/{provider}/countries",
    response_model=List[CountryInfo],
    summary="Get list of available countries",
    description="Retrieves a list of all countries that have VPN servers available, with code and name.",
)
async def get_available_countries(
    service: AbstractVPNService = Depends(get_vpn_service),
):
    """
    Retrieves a unique list of countries that have servers available
    for the specified provider.

    Returns country code, full name, and display format (e.g., "BR - Brazil").

    Useful for discovering which countries are supported before querying
    for specific country servers.
    """
    logger.info(f"Fetching available countries for {service.__class__.__name__}")

    servers = await service.get_servers()

    # Build unique country mapping (code -> name)
    country_map: Dict[str, str] = {}
    for server in servers:
        if server.country_code not in country_map:
            country_map[server.country_code] = server.country

    # Convert to CountryInfo objects, sorted by code
    countries = [
        CountryInfo(
            code=code,
            name=name,
            display=f"{code} - {name}",
        )
        for code, name in sorted(country_map.items())
    ]

    logger.info(f"Found {len(countries)} countries with available servers")

    return countries
