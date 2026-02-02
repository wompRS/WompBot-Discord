"""
Simple file-based bug tracker for WompBot
Only Wompie can report bugs via /bug command
"""
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

BUG_FILE = "/app/data/bugs.json"


def _ensure_data_dir():
    """Ensure data directory exists"""
    os.makedirs(os.path.dirname(BUG_FILE), exist_ok=True)


def _load_bugs() -> Dict[str, Any]:
    """Load bugs from file"""
    _ensure_data_dir()
    if os.path.exists(BUG_FILE):
        try:
            with open(BUG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"next_id": 1, "bugs": []}
    return {"next_id": 1, "bugs": []}


def _save_bugs(data: Dict[str, Any]):
    """Save bugs to file"""
    _ensure_data_dir()
    with open(BUG_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def report_bug(description: str, reporter: str, guild_name: Optional[str] = None,
               channel_name: Optional[str] = None, priority: str = "normal") -> int:
    """
    Report a new bug

    Returns:
        Bug ID
    """
    data = _load_bugs()
    bug_id = data["next_id"]

    bug = {
        "id": bug_id,
        "description": description,
        "reporter": reporter,
        "guild": guild_name,
        "channel": channel_name,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "resolved_at": None,
        "notes": []
    }

    data["bugs"].append(bug)
    data["next_id"] = bug_id + 1
    _save_bugs(data)

    print(f"Bug #{bug_id} reported: {description[:50]}...")
    return bug_id


def get_bug(bug_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific bug by ID"""
    data = _load_bugs()
    for bug in data["bugs"]:
        if bug["id"] == bug_id:
            return bug
    return None


def list_bugs(status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    List bugs, optionally filtered by status

    Args:
        status: 'open', 'resolved', 'wontfix', or None for all
        limit: Max bugs to return
    """
    data = _load_bugs()
    bugs = data["bugs"]

    if status:
        bugs = [b for b in bugs if b["status"] == status]

    # Return most recent first
    return sorted(bugs, key=lambda x: x["created_at"], reverse=True)[:limit]


def resolve_bug(bug_id: int, resolution: str = "fixed") -> bool:
    """
    Mark a bug as resolved

    Args:
        bug_id: Bug ID to resolve
        resolution: 'fixed', 'wontfix', 'duplicate', 'invalid'
    """
    data = _load_bugs()
    for bug in data["bugs"]:
        if bug["id"] == bug_id:
            bug["status"] = resolution
            bug["resolved_at"] = datetime.now().isoformat()
            _save_bugs(data)
            print(f"Bug #{bug_id} marked as {resolution}")
            return True
    return False


def add_note(bug_id: int, note: str, author: str) -> bool:
    """Add a note to a bug"""
    data = _load_bugs()
    for bug in data["bugs"]:
        if bug["id"] == bug_id:
            bug["notes"].append({
                "text": note,
                "author": author,
                "timestamp": datetime.now().isoformat()
            })
            _save_bugs(data)
            return True
    return False


def get_stats() -> Dict[str, int]:
    """Get bug statistics"""
    data = _load_bugs()
    bugs = data["bugs"]

    return {
        "total": len(bugs),
        "open": len([b for b in bugs if b["status"] == "open"]),
        "fixed": len([b for b in bugs if b["status"] == "fixed"]),
        "wontfix": len([b for b in bugs if b["status"] == "wontfix"]),
    }
