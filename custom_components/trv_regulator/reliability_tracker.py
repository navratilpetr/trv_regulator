"""Comprehensive TRV communication reliability tracker."""
import logging
from collections import deque, defaultdict
from datetime import datetime, timedelta
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class ReliabilityTracker:
    """Comprehensive TRV communication reliability tracker."""

    def __init__(self, room_name: str):
        """Initialize reliability tracker."""
        self._room_name = room_name
        
        # Counters
        self._commands_sent_total = 0
        self._commands_failed_total = 0
        self._watchdog_corrections_total = 0
        
        # Per-TRV tracking
        self._per_trv_sent = defaultdict(int)
        self._per_trv_failed = defaultdict(int)
        self._per_trv_last_seen = {}
        
        # Multi-window event queues with timestamps
        # Events format: {"type": "sent|failed|correction", "entity_id": str, "timestamp": float, ...}
        self._events_1h = deque(maxlen=200)
        self._events_24h = deque(maxlen=2000)
        self._events_7d = deque(maxlen=10000)
        self._events_30d = deque(maxlen=50000)
        
        # Aggregated statistics
        self._hourly_stats = deque(maxlen=720)  # 30 days
        self._daily_stats = deque(maxlen=30)
        
        # History
        self._command_history = deque(maxlen=100)
        self._correction_history = deque(maxlen=100)

    def command_sent(self, entity_id: str):
        """Track command sent to TRV."""
        now = datetime.now()
        timestamp = now.timestamp()
        
        self._commands_sent_total += 1
        self._per_trv_sent[entity_id] += 1
        self._per_trv_last_seen[entity_id] = now.isoformat()
        
        # Add event to all windows
        event = {
            "type": "sent",
            "entity_id": entity_id,
            "timestamp": timestamp,
        }
        self._events_1h.append(event)
        self._events_24h.append(event)
        self._events_7d.append(event)
        self._events_30d.append(event)

    def command_failed(self, entity_id: str, expected: dict, actual: dict):
        """Track failed command."""
        now = datetime.now()
        timestamp = now.timestamp()
        
        self._commands_failed_total += 1
        self._per_trv_failed[entity_id] += 1
        
        # Add event to all windows
        event = {
            "type": "failed",
            "entity_id": entity_id,
            "timestamp": timestamp,
        }
        self._events_1h.append(event)
        self._events_24h.append(event)
        self._events_7d.append(event)
        self._events_30d.append(event)
        
        # Add to command history
        self._command_history.append({
            "timestamp": now.isoformat(),
            "trv_entity": entity_id,
            "command": expected,
            "success": False,
            "actual_state": actual,
        })

    def watchdog_correction(self, entity_id: str, expected: dict, found: dict):
        """Track watchdog correction."""
        now = datetime.now()
        timestamp = now.timestamp()
        
        self._watchdog_corrections_total += 1
        
        # Add event to all windows
        event = {
            "type": "correction",
            "entity_id": entity_id,
            "timestamp": timestamp,
        }
        self._events_1h.append(event)
        self._events_24h.append(event)
        self._events_7d.append(event)
        self._events_30d.append(event)
        
        # Add to correction history
        self._correction_history.append({
            "timestamp": now.isoformat(),
            "trv_entity": entity_id,
            "expected": expected,
            "found": found,
            "corrected": True,
        })

    def _cleanup_old_events(self):
        """Clean up events older than their window."""
        now = datetime.now().timestamp()
        
        # 1 hour window
        cutoff_1h = now - 3600
        while self._events_1h and self._events_1h[0]["timestamp"] < cutoff_1h:
            self._events_1h.popleft()
        
        # 24 hours window
        cutoff_24h = now - 86400
        while self._events_24h and self._events_24h[0]["timestamp"] < cutoff_24h:
            self._events_24h.popleft()
        
        # 7 days window
        cutoff_7d = now - 604800
        while self._events_7d and self._events_7d[0]["timestamp"] < cutoff_7d:
            self._events_7d.popleft()
        
        # 30 days window
        cutoff_30d = now - 2592000
        while self._events_30d and self._events_30d[0]["timestamp"] < cutoff_30d:
            self._events_30d.popleft()

    def _count_events_in_window(self, events: deque, event_type: Optional[str] = None) -> int:
        """Count events of a specific type in a window."""
        if event_type is None:
            return len(events)
        return sum(1 for e in events if e["type"] == event_type)

    def _calculate_signal_quality(self, total: int, failed: int) -> tuple[str, float]:
        """Calculate signal quality and success rate."""
        if total == 0:
            return "unknown", 0.0
        
        success_rate = ((total - failed) / total) * 100
        
        if success_rate >= 98:
            signal_quality = "strong"
        elif success_rate >= 90:
            signal_quality = "medium"
        else:
            signal_quality = "weak"
        
        return signal_quality, success_rate

    def _calculate_trend(self) -> str:
        """Analyze signal quality trend (improving/stable/deteriorating)."""
        # Compare last 7 days with previous 7 days using daily stats
        if len(self._daily_stats) < 7:
            return "unknown"
        
        # Get last 7 days
        recent_stats = list(self._daily_stats)[-7:]
        recent_rates = [s.get("avg_reliability_rate", 0) for s in recent_stats]
        
        # Get previous 7 days if available
        if len(self._daily_stats) < 14:
            # Not enough data for comparison
            avg_recent = sum(recent_rates) / len(recent_rates) if recent_rates else 0
            if avg_recent >= 98:
                return "stable"
            elif avg_recent >= 90:
                return "stable"
            else:
                return "stable"
        
        previous_stats = list(self._daily_stats)[-14:-7]
        previous_rates = [s.get("avg_reliability_rate", 0) for s in previous_stats]
        
        avg_recent = sum(recent_rates) / len(recent_rates) if recent_rates else 0
        avg_previous = sum(previous_rates) / len(previous_rates) if previous_rates else 0
        
        # Calculate change
        change = avg_recent - avg_previous
        
        if change > 2:  # Improvement of more than 2%
            return "improving"
        elif change < -2:  # Degradation of more than 2%
            return "deteriorating"
        else:
            return "stable"

    def _aggregate_hourly_stats(self):
        """Aggregate events into hourly statistics."""
        # Get current hour
        now = datetime.now()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        
        # Check if we already have stats for current hour
        if self._hourly_stats and self._hourly_stats[-1]["hour"] == current_hour.isoformat():
            # Update existing hour
            self._hourly_stats[-1]["commands_sent"] = self._count_events_in_window(self._events_1h, "sent")
            self._hourly_stats[-1]["commands_failed"] = self._count_events_in_window(self._events_1h, "failed")
            self._hourly_stats[-1]["watchdog_corrections"] = self._count_events_in_window(self._events_1h, "correction")
        else:
            # Create new hour entry
            self._hourly_stats.append({
                "hour": current_hour.isoformat(),
                "commands_sent": self._count_events_in_window(self._events_1h, "sent"),
                "commands_failed": self._count_events_in_window(self._events_1h, "failed"),
                "watchdog_corrections": self._count_events_in_window(self._events_1h, "correction"),
            })

    def _aggregate_daily_stats(self):
        """Aggregate hourly stats into daily statistics."""
        if not self._hourly_stats:
            return
        
        # Get current day
        now = datetime.now()
        current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Aggregate hourly stats for today
        today_stats = [
            s for s in self._hourly_stats
            if datetime.fromisoformat(s["hour"]).date() == current_day.date()
        ]
        
        if not today_stats:
            return
        
        total_sent = sum(s["commands_sent"] for s in today_stats)
        total_failed = sum(s["commands_failed"] for s in today_stats)
        total_corrections = sum(s["watchdog_corrections"] for s in today_stats)
        
        avg_reliability = ((total_sent - total_failed) / total_sent * 100) if total_sent > 0 else 0
        
        # Check if we already have stats for today
        if self._daily_stats and self._daily_stats[-1]["date"] == current_day.date().isoformat():
            # Update existing day
            self._daily_stats[-1].update({
                "commands_sent": total_sent,
                "commands_failed": total_failed,
                "watchdog_corrections": total_corrections,
                "avg_reliability_rate": round(avg_reliability, 1),
            })
        else:
            # Create new day entry
            self._daily_stats.append({
                "date": current_day.date().isoformat(),
                "commands_sent": total_sent,
                "commands_failed": total_failed,
                "watchdog_corrections": total_corrections,
                "avg_reliability_rate": round(avg_reliability, 1),
            })

    def get_metrics(self) -> dict:
        """Get all current metrics."""
        # Cleanup old events
        self._cleanup_old_events()
        
        # Aggregate stats
        self._aggregate_hourly_stats()
        self._aggregate_daily_stats()
        
        # Calculate overall signal quality
        signal_quality, reliability_rate = self._calculate_signal_quality(
            self._commands_sent_total,
            self._commands_failed_total
        )
        
        # Calculate trend
        signal_trend = self._calculate_trend()
        
        # Calculate per-window statistics
        failed_1h = self._count_events_in_window(self._events_1h, "failed")
        failed_24h = self._count_events_in_window(self._events_24h, "failed")
        failed_7d = self._count_events_in_window(self._events_7d, "failed")
        failed_30d = self._count_events_in_window(self._events_30d, "failed")
        
        corrections_1h = self._count_events_in_window(self._events_1h, "correction")
        corrections_24h = self._count_events_in_window(self._events_24h, "correction")
        corrections_7d = self._count_events_in_window(self._events_7d, "correction")
        corrections_30d = self._count_events_in_window(self._events_30d, "correction")
        
        sent_1h = self._count_events_in_window(self._events_1h, "sent")
        sent_24h = self._count_events_in_window(self._events_24h, "sent")
        sent_7d = self._count_events_in_window(self._events_7d, "sent")
        sent_30d = self._count_events_in_window(self._events_30d, "sent")
        
        # Calculate per-TRV statistics
        trv_statistics = {}
        for entity_id in set(list(self._per_trv_sent.keys()) + list(self._per_trv_failed.keys())):
            sent = self._per_trv_sent.get(entity_id, 0)
            failed = self._per_trv_failed.get(entity_id, 0)
            quality, rate = self._calculate_signal_quality(sent, failed)
            
            trv_statistics[entity_id] = {
                "commands_sent": sent,
                "commands_failed": failed,
                "success_rate": round(rate, 1),
                "signal_quality": quality,
                "last_seen": self._per_trv_last_seen.get(entity_id),
            }
        
        return {
            # Overall metrics
            "commands_sent_total": self._commands_sent_total,
            "commands_failed_total": self._commands_failed_total,
            "watchdog_corrections_total": self._watchdog_corrections_total,
            "reliability_rate": round(reliability_rate, 1),
            "signal_quality": signal_quality,
            "signal_trend": signal_trend,
            
            # Multi-window statistics
            "failed_commands_1h": failed_1h,
            "failed_commands_24h": failed_24h,
            "failed_commands_7d": failed_7d,
            "failed_commands_30d": failed_30d,
            
            "watchdog_corrections_1h": corrections_1h,
            "watchdog_corrections_24h": corrections_24h,
            "watchdog_corrections_7d": corrections_7d,
            "watchdog_corrections_30d": corrections_30d,
            
            "commands_sent_1h": sent_1h,
            "commands_sent_24h": sent_24h,
            "commands_sent_7d": sent_7d,
            "commands_sent_30d": sent_30d,
            
            # Aggregated statistics
            "hourly_stats": list(self._hourly_stats),
            "daily_stats": list(self._daily_stats),
            
            # History
            "command_history": list(self._command_history),
            "correction_history": list(self._correction_history),
            
            # Per-TRV statistics
            "trv_statistics": trv_statistics,
        }

    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        return {
            "commands_sent_total": self._commands_sent_total,
            "commands_failed_total": self._commands_failed_total,
            "watchdog_corrections_total": self._watchdog_corrections_total,
            
            "per_trv_sent": dict(self._per_trv_sent),
            "per_trv_failed": dict(self._per_trv_failed),
            "per_trv_last_seen": dict(self._per_trv_last_seen),
            
            "events_30d": list(self._events_30d),
            
            "hourly_stats": list(self._hourly_stats),
            "daily_stats": list(self._daily_stats),
            
            "command_history": list(self._command_history),
            "correction_history": list(self._correction_history),
        }

    @classmethod
    def from_dict(cls, room_name: str, data: dict):
        """Deserialize from JSON storage."""
        tracker = cls(room_name)
        
        # Restore counters
        tracker._commands_sent_total = data.get("commands_sent_total", 0)
        tracker._commands_failed_total = data.get("commands_failed_total", 0)
        tracker._watchdog_corrections_total = data.get("watchdog_corrections_total", 0)
        
        # Restore per-TRV tracking
        tracker._per_trv_sent = defaultdict(int, data.get("per_trv_sent", {}))
        tracker._per_trv_failed = defaultdict(int, data.get("per_trv_failed", {}))
        tracker._per_trv_last_seen = data.get("per_trv_last_seen", {})
        
        # Restore events from 30d window and populate other windows
        events_30d = data.get("events_30d", [])
        now = datetime.now().timestamp()
        
        for event in events_30d:
            timestamp = event["timestamp"]
            
            # Add to 30d window
            tracker._events_30d.append(event)
            
            # Add to appropriate windows based on age
            if now - timestamp <= 3600:  # 1 hour
                tracker._events_1h.append(event)
            if now - timestamp <= 86400:  # 24 hours
                tracker._events_24h.append(event)
            if now - timestamp <= 604800:  # 7 days
                tracker._events_7d.append(event)
        
        # Restore aggregated stats
        tracker._hourly_stats = deque(data.get("hourly_stats", []), maxlen=720)
        tracker._daily_stats = deque(data.get("daily_stats", []), maxlen=30)
        
        # Restore history
        tracker._command_history = deque(data.get("command_history", []), maxlen=100)
        tracker._correction_history = deque(data.get("correction_history", []), maxlen=100)
        
        return tracker
