"""The Procare Activities integration."""
import asyncio
import json
import logging
from datetime import time, timedelta
from pathlib import Path
import aiohttp

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_SCHOOL_NAME,
    CONF_UPDATE_INTERVAL,
    CONF_AFTER_HOURS_INTERVAL,
    CONF_OPERATING_START,
    CONF_OPERATING_END,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_AFTER_HOURS_INTERVAL,
    DEFAULT_OPERATING_START,
    DEFAULT_OPERATING_END,
)
from .api import ProcareApi, ProcareApiError, ProcareAuthError

_LOGGER = logging.getLogger(__name__)

CARD_FILENAME = "procare-timeline-card.js"
CARD_URL_PATH = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_REGISTERED_KEY = f"{DOMAIN}_card_registered"


async def _register_timeline_card(hass: HomeAssistant) -> None:
    """Serve the Lovelace card from the integration and inject it on every page."""
    if hass.data.get(CARD_REGISTERED_KEY):
        return
    hass.data[CARD_REGISTERED_KEY] = True

    card_path = Path(__file__).parent / CARD_FILENAME
    if not card_path.is_file():
        _LOGGER.warning("Timeline card file missing at %s; skipping auto-registration", card_path)
        return

    try:
        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text())
        version = manifest.get("version", "0")
    except Exception:
        version = "0"

    try:
        from homeassistant.components.http import StaticPathConfig
        await hass.http.async_register_static_paths([
            StaticPathConfig(CARD_URL_PATH, str(card_path), False)
        ])
    except ImportError:
        # Older HA cores: synchronous API.
        hass.http.register_static_path(CARD_URL_PATH, str(card_path), False)

    add_extra_js_url(hass, f"{CARD_URL_PATH}?v={version}")
    _LOGGER.info("Procare timeline card auto-registered at %s", CARD_URL_PATH)


def _opt(entry: ConfigEntry, key: str, default):
    return entry.options.get(key, entry.data.get(key, default))


def _parse_time(value) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(value)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Procare Activities from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _register_timeline_card(hass)
    
    username = entry.data["username"]
    password = entry.data["password"]
    selected_kid_id = entry.data["kid_id"]
    school_name = entry.data.get(CONF_SCHOOL_NAME)

    # Create a single, persistent session for the integration
    session = aiohttp.ClientSession()
    api = ProcareApi(session, username, password, school_name)

    def current_interval() -> timedelta:
        """Pick poll interval based on whether HA local time is within operating hours."""
        in_hours = _opt(entry, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        after_hours = _opt(entry, CONF_AFTER_HOURS_INTERVAL, DEFAULT_AFTER_HOURS_INTERVAL)
        start = _parse_time(_opt(entry, CONF_OPERATING_START, DEFAULT_OPERATING_START))
        end = _parse_time(_opt(entry, CONF_OPERATING_END, DEFAULT_OPERATING_END))
        now = dt_util.now().time()
        if start <= end:
            within = start <= now < end
        else:
            within = now >= start or now < end
        return timedelta(minutes=in_hours if within else after_hours)

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            result = await api.async_get_activities(selected_kid_id)
        except ProcareAuthError as err:
            raise ConfigEntryAuthFailed from err
        except ProcareApiError as err:
            raise UpdateFailed(f"Error communicating with Procare API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
        # Adjust the interval used to schedule the next refresh.
        coordinator.update_interval = current_interval()
        return result

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="procare_activities_sensor",
        update_method=async_update_data,
        update_interval=current_interval(),
    )

    # Fetch initial data so we have it when platforms are set up.
    await coordinator.async_refresh()

    # Store the coordinator and the session together
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "session": session
    }

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Use the modern method to forward the setup to all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Correctly unload all platforms associated with the config entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Properly close the session and remove the entry data
        await hass.data[DOMAIN][entry.entry_id]["session"].close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

