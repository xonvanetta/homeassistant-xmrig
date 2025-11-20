"""Support for REST API calls."""
import logging

import httpx

from homeassistant.helpers.httpx_client import get_async_client

DEFAULT_TIMEOUT = 30

_LOGGER = logging.getLogger(__name__)


class RestApiCall:
    """Class for handling the data retrieval."""

    def __init__(
        self,
        hass,
        method,
        resource,
        auth,
        headers,
        params,
        data,
        verify_ssl,
        timeout=DEFAULT_TIMEOUT,
    ):
        """Initialize the data object."""
        self._hass = hass
        self._method = method
        self._resource = resource
        self._auth = auth
        self._headers = headers
        self._params = params
        self._request_data = data
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._async_client = None
        self.data = None
        self.last_exception = None
        self.headers = None
        self.status = 0

        # Extract base address from resource URL for JSON-RPC calls
        # Resource format: http://host:port/2/summary -> http://host:port
        if resource:
            parts = resource.split("/2/")
            self._base_address = parts[0] if len(parts) > 1 else resource.rsplit("/", 1)[0]
        else:
            self._base_address = None

    async def _json_rpc(self, action: str) -> None:
        """Send JSON-RPC command to XMRig."""
        if not self._base_address:
            _LOGGER.error("Base address not available for JSON-RPC call")
            return

        if not self._async_client:
            self._async_client = get_async_client(
                self._hass, verify_ssl=self._verify_ssl
            )

        json_rpc_headers = self._headers.copy() if self._headers else {}
        json_rpc_headers["Content-Type"] = "application/json"

        try:
            response = await self._async_client.post(
                f"{self._base_address}/json_rpc",
                headers=json_rpc_headers,
                json={"method": action},
                timeout=5
            )
            if response.status_code != 200:
                _LOGGER.error(
                    f"JSON-RPC request failed: {response.status_code} {response.text}"
                )
        except httpx.RequestError as ex:
            _LOGGER.error(f"Exception during JSON-RPC call: {ex}")

    async def pause(self) -> None:
        """Pause XMRig mining."""
        await self._json_rpc("pause")

    async def resume(self) -> None:
        """Resume XMRig mining."""
        await self._json_rpc("resume")

    async def async_update(self, log_errors=True):
        """Get the latest data from REST service with provided method."""
        if not self._async_client:
            self._async_client = get_async_client(
                self._hass, verify_ssl=self._verify_ssl
            )

        _LOGGER.debug("Updating from %s", self._resource)
        try:
            response = await self._async_client.request(
                self._method,
                self._resource,
                headers=self._headers,
                params=self._params,
                auth=self._auth,
                data=self._request_data,
                timeout=self._timeout,
                follow_redirects=True,
            )
            self.data = response.text
            self.headers = response.headers
            self.status = response.status_code
        except httpx.RequestError as ex:
            if log_errors:
                _LOGGER.error(
                    "Error fetching data: %s failed with %s", self._resource, ex
                )
            self.last_exception = ex
            self.status = 500
            self.data = None
            self.headers = None
