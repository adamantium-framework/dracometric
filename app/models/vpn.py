# app/models/vpn.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

class VPNServer(BaseModel):
    """
    A canonical representation of a VPN server from any provider.
    """
    provider: Literal["nordvpn", "surfshark"] = Field(
        ...,
        description="The VPN provider."
    )
    country: str = Field(
        ...,
        description="The country where the server is located."
    )
    country_code: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="The two-letter country code."
    )
    identifier: str = Field(
        ...,
        description="The unique identifier for the server (e.g., hostname, IP address)."
    )
    public_key: str = Field(
        ...,
        description="The WireGuard public key for the server."
    )
    load: Optional[int] = Field(
        None,
        ge=0,
        description="The current server load percentage (0-100), if provided."
    )
    latency: Optional[float] = Field(
        None,
        ge=0,
        description="The server latency in milliseconds, if measured."
    )

    model_config = {"from_attributes": True}


class CountryInfo(BaseModel):
    """Country information with code and name."""

    code: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code."
    )
    name: str = Field(
        ...,
        description="Full country name."
    )
    display: str = Field(
        ...,
        description="Display format: 'CODE - Name'."
    )

