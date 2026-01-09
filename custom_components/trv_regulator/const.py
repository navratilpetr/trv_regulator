"""Konstanty pro TRV Regulator."""

# Stavy
STATE_IDLE = "idle"
STATE_HEATING = "heating"
STATE_VENT = "vent"
STATE_POST_VENT = "post_vent"

# TRV příkazy
TRV_ON = {"hvac_mode": "heat", "temperature": 35}
TRV_OFF = {"hvac_mode": "off", "temperature": 5}

# Proporcionální regulace
DEFAULT_GAIN = 40.0
DEFAULT_OFFSET = -0.1
MIN_GAIN = 10.0
MAX_GAIN = 80.0
MIN_OFFSET = -3.0
MAX_OFFSET = 3.0
TRV_MIN_TEMP = 5.0
TRV_MAX_TEMP = 35.0

# Výchozí hodnoty
DEFAULT_HYSTERESIS = 0.3
DEFAULT_VENT_DELAY = 120  # sekundy
DEFAULT_POST_VENT_DURATION = 300  # sekundy
DEFAULT_UPDATE_INTERVAL = 10  # sekundy
DEFAULT_ADAPTIVE_LEARNING = True

# Domain
DOMAIN = "trv_regulator"
