"""Home Assistant platform setup for XMRig switch."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DATA_CONTROLLER

_LOGGER = logging.getLogger(__name__)


class XmrigSwitch(SwitchEntity):
    """XMRig mining control switch entity."""

    def __init__(self, hass: HomeAssistant, controller):
        """Initialize the switch."""
        super().__init__()
        self._hass = hass
        self._controller = controller
        self._attr_name = "Mining"
        self._attr_unique_id = f"{controller.entity_id}_mining"
        self._is_paused = False

    @property
    def is_on(self):
        """Return True if mining is active (not paused)."""
        return not self._is_paused

    @property
    def icon(self):
        """Return icon based on state."""
        return "mdi:pickaxe" if self.is_on else "mdi:pause-circle"

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        return {
            "identifiers": {(DOMAIN, self._controller._name)},
            "name": self._controller._name,
        }

    async def async_turn_on(self, **kwargs):
        """Turn on the switch (start/resume mining)."""
        await self._controller._rest.resume()
        self._is_paused = False
        self.async_write_ha_state()
        _LOGGER.info("XMRig mining resumed via switch.")

        # Trigger immediate controller update to sync state
        await self._controller.async_Update()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch (pause mining)."""
        await self._controller._rest.pause()
        self._is_paused = True
        self.async_write_ha_state()
        _LOGGER.info("XMRig mining paused via switch.")

        # Trigger immediate controller update to sync state
        await self._controller.async_Update()

    async def async_update(self):
        """Update switch state from XMRig API."""
        if not self._controller.InError:
            paused_state = self._controller.GetData(["paused"])
            if paused_state is not None:
                old_state = self._is_paused
                self._is_paused = paused_state
                _LOGGER.info(
                    f"XMRig state sync: paused={self._is_paused} (was {old_state}), "
                    f"mining={'active' if not self._is_paused else 'paused'}"
                )
            else:
                _LOGGER.warning("Could not read paused state from XMRig API")

    async def async_added_to_hass(self):
        """Run when entity is added to hass."""
        _LOGGER.debug(f"async_added_to_hass({self._attr_name})")

        # Subscribe to controller updates
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                self._controller.UpdateSignal,
                self._handle_controller_update,
            )
        )

        # Initial state sync
        await self.async_update()

    @callback
    def _handle_controller_update(self):
        """Handle updated data from the controller."""
        if not self._controller.InError:
            paused_state = self._controller.GetData(["paused"])
            if paused_state is not None:
                if self._is_paused != paused_state:
                    _LOGGER.info(
                        f"XMRig state changed: paused={paused_state}, "
                        f"mining={'active' if not paused_state else 'paused'}"
                    )
                self._is_paused = paused_state
                self.async_write_ha_state()
            else:
                _LOGGER.debug("No paused state in controller data")

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    controller = hass.data[DOMAIN][DATA_CONTROLLER][config_entry.entry_id]
    async_add_entities([XmrigSwitch(hass, controller)], True)
