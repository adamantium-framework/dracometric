# app/services/latency_service.py
"""
Latency measurement service for VPN servers.

Supports multiple measurement methods:
1. fping (external command) - fastest for bulk measurements
2. TCP connect - fallback, no root required
3. ICMP ping (Python) - if available and has permissions
"""

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.models.vpn import VPNServer

logger = logging.getLogger(__name__)

# Default ports to try for TCP latency
WIREGUARD_PORT = 51820
FALLBACK_PORTS = [443, 80, 22]

# Timeouts
PING_TIMEOUT = 2.0  # seconds
TCP_TIMEOUT = 3.0  # seconds
FPING_TIMEOUT = 1000  # milliseconds


@dataclass
class LatencyResult:
    """Result of a latency measurement."""

    host: str
    latency_ms: Optional[float]  # None if unreachable
    method: str  # "fping", "tcp", "icmp"
    success: bool


class LatencyService:
    """Service for measuring server latency."""

    def __init__(self):
        self._fping_available: Optional[bool] = None
        self._lock = asyncio.Lock()

    @property
    def fping_available(self) -> bool:
        """Check if fping is available on the system."""
        if self._fping_available is None:
            self._fping_available = shutil.which("fping") is not None
            if self._fping_available:
                logger.info("fping detected - using for bulk latency measurements")
            else:
                logger.info("fping not found - using TCP fallback for latency")
        return self._fping_available

    async def measure_latency_bulk(
        self,
        servers: List[VPNServer],
        method: str = "auto",
    ) -> Dict[str, LatencyResult]:
        """
        Measure latency for multiple servers.

        Args:
            servers: List of VPN servers to measure
            method: "auto", "fping", "tcp", or "icmp"

        Returns:
            Dict mapping server identifier to LatencyResult
        """
        if not servers:
            return {}

        # Extract unique hosts
        hosts = list(set(self._extract_host(s.identifier) for s in servers))

        logger.info(f"Measuring latency for {len(hosts)} unique hosts using method={method}")

        if method == "auto":
            if self.fping_available:
                method = "fping"
            else:
                method = "tcp"

        if method == "fping":
            results = await self._measure_fping(hosts)
        elif method == "tcp":
            results = await self._measure_tcp_bulk(hosts)
        else:
            results = await self._measure_tcp_bulk(hosts)

        logger.info(
            f"Latency measurement complete: "
            f"{sum(1 for r in results.values() if r.success)}/{len(results)} successful"
        )

        return results

    async def measure_servers_latency(
        self,
        servers: List[VPNServer],
        method: str = "auto",
    ) -> List[VPNServer]:
        """
        Measure latency and update server objects.

        Args:
            servers: List of VPN servers
            method: Measurement method

        Returns:
            List of VPNServer objects with latency field populated
        """
        if not servers:
            return []

        # Measure latency for all servers
        results = await self.measure_latency_bulk(servers, method)

        # Update servers with latency data
        updated_servers = []
        for server in servers:
            host = self._extract_host(server.identifier)
            result = results.get(host)

            if result and result.success and result.latency_ms is not None:
                # Create new server with latency
                updated_server = server.model_copy(
                    update={"latency": round(result.latency_ms, 2)}
                )
            else:
                # Keep server without latency (or set to None)
                updated_server = server.model_copy(update={"latency": None})

            updated_servers.append(updated_server)

        return updated_servers

    def _extract_host(self, identifier: str) -> str:
        """Extract hostname/IP from identifier."""
        # Remove protocol if present
        if "://" in identifier:
            identifier = identifier.split("://")[1]
        # Remove port if present
        if ":" in identifier:
            identifier = identifier.split(":")[0]
        # Remove path if present
        if "/" in identifier:
            identifier = identifier.split("/")[0]
        return identifier

    async def _measure_fping(self, hosts: List[str]) -> Dict[str, LatencyResult]:
        """
        Use fping for bulk latency measurement.

        fping is very efficient for measuring many hosts at once.
        Batches requests to avoid command line length limits.
        """
        if not hosts:
            return {}

        results: Dict[str, LatencyResult] = {}

        # Batch size to avoid command line length limits (~200KB on Linux)
        # Each hostname is ~20-30 chars, so 500 hosts ≈ 15KB (safe margin)
        batch_size = 500

        try:
            for i in range(0, len(hosts), batch_size):
                batch = hosts[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(hosts) + batch_size - 1) // batch_size

                if total_batches > 1:
                    logger.info(f"fping batch {batch_num}/{total_batches} ({len(batch)} hosts)")

                batch_results = await self._measure_fping_batch(batch)
                results.update(batch_results)

            # Check if any measurements succeeded
            success_count = sum(1 for r in results.values() if r.success)
            if success_count == 0 and len(hosts) > 0:
                logger.warning("fping returned no successful results, falling back to TCP")
                return await self._measure_tcp_bulk(hosts)

        except Exception as e:
            logger.error(f"fping error: {e}, falling back to TCP")
            return await self._measure_tcp_bulk(hosts)

        return results

    async def _measure_fping_batch(self, hosts: List[str]) -> Dict[str, LatencyResult]:
        """Measure a single batch of hosts with fping."""
        results: Dict[str, LatencyResult] = {}

        try:
            # fping options:
            # -c 1: send 1 ping
            # -t: timeout in ms
            # -q: quiet mode
            # -e: show elapsed time
            cmd = [
                "fping",
                "-c", "1",
                "-t", str(FPING_TIMEOUT),
                "-q",
                "-e",
            ] + hosts

            logger.debug(f"Running fping for {len(hosts)} hosts")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Timeout: base 10s + 50ms per host (for DNS resolution + ping)
            timeout = 10 + len(hosts) * 0.05
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            # fping outputs to stderr
            output = stderr.decode("utf-8", errors="ignore")

            # Parse fping output
            # Format: "host : xmt/rcv/%loss = 1/1/0%, min/avg/max = 10.5/10.5/10.5"
            # Or: "host : xmt/rcv/%loss = 1/0/100%"
            for line in output.strip().split("\n"):
                if not line.strip():
                    continue

                try:
                    parts = line.split(":")
                    if len(parts) < 2:
                        continue

                    host = parts[0].strip()

                    if "100%" in line:
                        # Host unreachable
                        results[host] = LatencyResult(
                            host=host,
                            latency_ms=None,
                            method="fping",
                            success=False,
                        )
                    elif "min/avg/max" in line:
                        # Parse latency
                        avg_part = line.split("min/avg/max")[1]
                        latency_str = avg_part.split("/")[1].strip()
                        latency = float(latency_str)
                        results[host] = LatencyResult(
                            host=host,
                            latency_ms=latency,
                            method="fping",
                            success=True,
                        )
                except Exception as e:
                    logger.debug(f"Failed to parse fping line '{line}': {e}")
                    continue

            # Add missing hosts as failed
            for host in hosts:
                if host not in results:
                    results[host] = LatencyResult(
                        host=host,
                        latency_ms=None,
                        method="fping",
                        success=False,
                    )

        except asyncio.TimeoutError:
            logger.warning(f"fping batch timed out for {len(hosts)} hosts")
            # Mark all as failed
            for host in hosts:
                if host not in results:
                    results[host] = LatencyResult(
                        host=host,
                        latency_ms=None,
                        method="fping",
                        success=False,
                    )

        return results

    async def _measure_tcp_bulk(
        self,
        hosts: List[str],
        max_concurrent: int = 50,
    ) -> Dict[str, LatencyResult]:
        """
        Measure latency using TCP connect for multiple hosts.

        This doesn't require root privileges.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def measure_one(host: str) -> Tuple[str, LatencyResult]:
            async with semaphore:
                result = await self._measure_tcp_single(host)
                return host, result

        tasks = [measure_one(host) for host in hosts]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results: Dict[str, LatencyResult] = {}
        for item in results_list:
            if isinstance(item, Exception):
                logger.debug(f"TCP measurement exception: {item}")
                continue
            host, result = item
            results[host] = result

        return results

    async def _measure_tcp_single(self, host: str) -> LatencyResult:
        """Measure latency to a single host using TCP connect."""
        ports_to_try = [WIREGUARD_PORT] + FALLBACK_PORTS

        for port in ports_to_try:
            try:
                start = time.perf_counter()

                # Create connection with timeout
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=TCP_TIMEOUT,
                )

                end = time.perf_counter()
                latency_ms = (end - start) * 1000

                writer.close()
                await writer.wait_closed()

                return LatencyResult(
                    host=host,
                    latency_ms=latency_ms,
                    method=f"tcp:{port}",
                    success=True,
                )

            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                continue

        # All ports failed
        return LatencyResult(
            host=host,
            latency_ms=None,
            method="tcp",
            success=False,
        )


# Singleton instance
_latency_service: Optional[LatencyService] = None


def get_latency_service() -> LatencyService:
    """Get the singleton LatencyService instance."""
    global _latency_service
    if _latency_service is None:
        _latency_service = LatencyService()
    return _latency_service
