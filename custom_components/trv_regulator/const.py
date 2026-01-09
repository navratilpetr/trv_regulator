"""Konstanty pro TRV Regulator."""

# Stavy
STATE_IDLE = "idle"
STATE_HEATING = "heating"
STATE_VENT = "vent"
STATE_POST_VENT = "post_vent"

# TRV příkazy
TRV_ON = {"hvac_mode": "heat", "temperature": 35}
TRV_OFF = {"hvac_mode": "off", "temperature": 5}

# Výchozí hodnoty
DEFAULT_HYSTERESIS = 0.3
DEFAULT_VENT_DELAY = 120  # sekundy
DEFAULT_POST_VENT_DURATION = 300  # sekundy

# Domain
DOMAIN = "trv_regulator"
