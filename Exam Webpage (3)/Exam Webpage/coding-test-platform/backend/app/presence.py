"""
Real-time Team Presence & Heartbeat Tracker
Tracks live online status and active exam participation across all teams.
"""
from datetime import datetime, timedelta
from typing import Dict, Set

# In-memory thread-safe dictionary mapping team_id -> last_heartbeat_datetime (UTC)
TEAM_HEARTBEATS: Dict[int, datetime] = {}

HEARTBEAT_TIMEOUT_SECONDS = 20

def record_team_heartbeat(team_id: int):
    """Record that a team is currently online and active in their browser"""
    TEAM_HEARTBEATS[team_id] = datetime.utcnow()

def is_team_online(team_id: int) -> bool:
    """Check if a team has sent a heartbeat within the timeout window"""
    last_hb = TEAM_HEARTBEATS.get(team_id)
    if not last_hb:
        return False
    return (datetime.utcnow() - last_hb).total_seconds() <= HEARTBEAT_TIMEOUT_SECONDS

def get_online_team_ids() -> Set[int]:
    """Get all team IDs that are currently online and connected"""
    now = datetime.utcnow()
    return {
        tid for tid, last_hb in TEAM_HEARTBEATS.items()
        if (now - last_hb).total_seconds() <= HEARTBEAT_TIMEOUT_SECONDS
    }

def clear_team_presence(team_id: int):
    """Clear a team's online presence (e.g. on logout or reset)"""
    if team_id in TEAM_HEARTBEATS:
        del TEAM_HEARTBEATS[team_id]
