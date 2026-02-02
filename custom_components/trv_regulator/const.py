"""Konstanty pro TRV Regulator."""

# Stavy
STATE_IDLE = "idle"
STATE_HEATING = "heating"
STATE_COOLDOWN = "cooldown"
STATE_VENT = "vent"
STATE_ERROR = "error"

# TRV příkazy
TRV_ON = {"hvac_mode": "heat", "temperature": 35}
TRV_OFF = {"hvac_mode": "heat", "temperature": 5}

# Výchozí hodnoty
DEFAULT_HYSTERESIS = 0.3
DEFAULT_WINDOW_OPEN_DELAY = 120  # sekundy
DEFAULT_UPDATE_INTERVAL = 30  # sekundy

# Učící algoritmus
DEFAULT_LEARNING_CYCLES = 10
DEFAULT_DESIRED_OVERSHOOT = 0.1  # °C
DEFAULT_MIN_HEATING_DURATION = 180  # sekund (3 min)
DEFAULT_MAX_HEATING_DURATION = 7200  # sekund (120 min)
DEFAULT_MAX_VALID_OVERSHOOT = 3.0  # °C
DEFAULT_COOLDOWN_DURATION = 1200  # sekund (20 min)

# Historie a persistence
HISTORY_SIZE = 100
STORAGE_DIR = ".storage"
STORAGE_FILE = "trv_regulator_learned_params.json"

# Timeouty pro error handling
SENSOR_OFFLINE_TIMEOUT = 120  # sekund (2 min)
TRV_OFFLINE_TIMEOUT = 300  # sekund (5 min)
TARGET_DEBOUNCE_DELAY = 15  # sekund
TRV_COMMAND_VERIFY_DELAY = 5  # sekund - čekání na potvrzení TRV příkazu
TRV_TEMP_TOLERANCE = 1  # °C - tolerance pro kontrolu teploty TRV

# Domain
DOMAIN = "trv_regulator"
