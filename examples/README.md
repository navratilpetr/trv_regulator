# TRV Regulator - UI Examples

This folder contains ready-to-use Lovelace card configurations for visualizing TRV reliability metrics.

## Available Examples

### 1. `lovelace_gauge.yaml` - Simple Gauge Indicator

A clean gauge showing the current signal quality percentage with color-coded severity levels.

**Usage:**
```yaml
# Add to your Lovelace dashboard
# Replace 'loznice' with your room name
type: gauge
entity: sensor.trv_regulator_YOUR_ROOM_reliability
attribute: reliability_rate
name: TRV Signal Quality
min: 0
max: 100
needle: true
severity:
  green: 98
  yellow: 90
  red: 0
```

### 2. `lovelace_complete.yaml` - Complete Dashboard

A comprehensive dashboard showing:
- Overall signal quality gauge
- Individual TRV status (glance card)
- Detailed metrics (failed commands, auto-corrections, trend)

**Usage:**
```yaml
# Add to your Lovelace dashboard
# Replace entity names with your actual room and TRV names
```

**Note:** You'll need to update the entity IDs in the glance section to match your actual TRV entities:
```yaml
entities:
  - entity: sensor.trv_YOUR_TRV_1_reliability
    name: TRV 1
  - entity: sensor.trv_YOUR_TRV_2_reliability
    name: TRV 2
```

### 3. `lovelace_apexcharts.yaml` - Trend Graph

Beautiful trend visualization showing reliability over the last 7 days.

**Requirements:**
- Install [ApexCharts Card](https://github.com/RomRider/apexcharts-card) from HACS

**Usage:**
```yaml
# Install ApexCharts Card via HACS first
# Then add this card to your dashboard
# Replace 'loznice' with your room name
```

## Entity Naming Convention

TRV Regulator creates the following sensors for each room:

### Aggregate Reliability Sensor
```
sensor.trv_regulator_{ROOM_NAME}_reliability
```

**State:** `weak` / `medium` / `strong` / `unknown`

**Attributes:**
- `reliability_rate`: Success percentage (0-100)
- `signal_quality`: weak / medium / strong
- `failed_commands_1h/24h/7d/30d`: Failed commands in time windows
- `watchdog_corrections_1h/24h/7d/30d`: Auto-corrections in time windows
- `commands_sent_1h/24h/7d/30d`: Total commands in time windows
- `signal_trend`: improving / stable / deteriorating
- `trv_statistics`: Per-TRV detailed statistics
- `hourly_stats`: Last 720 hours (30 days)
- `daily_stats`: Last 30 days
- `command_history`: Last 100 commands
- `correction_history`: Last 100 corrections

### Per-TRV Reliability Sensors
```
sensor.{TRV_NAME}_reliability
```

**State:** `weak` / `medium` / `strong` / `unknown`

**Attributes:**
- `commands_sent`: Total commands sent to this TRV
- `commands_failed`: Total failed commands
- `success_rate`: Success percentage
- `signal_quality`: weak / medium / strong
- `last_seen`: Last command timestamp

## Understanding Signal Quality

### Strong (≥98% success rate)
- ✅ Excellent Zigbee signal
- ✅ Very rare command failures
- ✅ No action needed

### Medium (90-98% success rate)
- ⚠️ Acceptable but not ideal
- ⚠️ Occasional command failures
- 💡 Consider adding a Zigbee router nearby

### Weak (<90% success rate)
- ❌ Poor Zigbee signal
- ❌ Frequent command failures
- ❌ High number of auto-corrections
- 🔧 **Action Required:**
  1. Check `trv_statistics` to identify problematic TRVs
  2. Add Zigbee router/repeater near affected TRVs
  3. Monitor `signal_trend` - should improve after adding router

## Troubleshooting

### "Unknown" Signal Quality
This means there's not enough data yet. The system needs a few commands to calculate reliability.

### High Watchdog Corrections
Auto-corrections indicate that TRVs frequently stay in the wrong state, usually due to:
- Weak Zigbee signal
- Interference from other devices
- TRV too far from coordinator

**Solution:** Add Zigbee router/repeater to strengthen the mesh network.

### Deteriorating Trend
If `signal_trend` shows "deteriorating":
1. Check for new sources of interference
2. Verify Zigbee network health
3. Check battery levels in TRVs
4. Consider repositioning Zigbee routers

## Integration with Automations

### Example: Alert on Weak Signal

```yaml
automation:
  - alias: "TRV Signal Quality Alert"
    trigger:
      - platform: state
        entity_id: sensor.trv_regulator_loznice_reliability
        to: "weak"
        for:
          hours: 1
    action:
      - service: notify.mobile_app
        data:
          title: "TRV Signal Warning"
          message: >
            {{ trigger.entity_id }} has weak signal quality.
            Check TRV statistics for details.
```

### Example: Track Failed Commands

```yaml
automation:
  - alias: "TRV Failed Commands Monitor"
    trigger:
      - platform: state
        entity_id: sensor.trv_regulator_loznice_reliability
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.trv_regulator_loznice_reliability', 'failed_commands_24h') | int > 10 }}
    action:
      - service: persistent_notification.create
        data:
          title: "High TRV Command Failures"
          message: >
            {{ state_attr('sensor.trv_regulator_loznice_reliability', 'failed_commands_24h') }}
            failed commands in the last 24 hours. Check Zigbee network.
```

## More Information

See the main [README.md](../README.md) for complete documentation.
