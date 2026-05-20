"""Constants for the Procare Activities integration."""

DOMAIN = "procare_activities"
PLATFORMS = ["sensor"]

CONF_SCHOOL_NAME = "school_name"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_AFTER_HOURS_INTERVAL = "after_hours_interval"
CONF_OPERATING_START = "operating_start"
CONF_OPERATING_END = "operating_end"
DEFAULT_UPDATE_INTERVAL = 35  # keep original default, minutes
DEFAULT_AFTER_HOURS_INTERVAL = 60  # minutes
DEFAULT_OPERATING_START = "07:00:00"
DEFAULT_OPERATING_END = "18:00:00"

DEFAULT_AUTH_HOST = "https://online-auth.procareconnect.com"
DEFAULT_API_HOST = "https://api-school.procareconnect.com"
DEFAULT_WEB_HOST = "https://schools.procareconnect.com"

