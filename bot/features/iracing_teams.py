"""
iRacing Team Management System
Handles team creation, member management, events, and scheduling
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
import discord


class iRacingTeamManager:
    """Manages iRacing teams, events, and driver scheduling"""

    def __init__(self, db):
        self.db = db

    # ==================== TEAM MANAGEMENT ====================

    def create_team(self, guild_id: int, team_name: str, team_tag: str, created_by: int, description: str = None) -> Optional[int]:
        """
        Create a new iRacing team

        Args:
            guild_id: Discord server ID
            team_name: Name of the team
            team_tag: Short team abbreviation
            created_by: Discord user ID of creator
            description: Optional team description

        Returns:
            Team ID if successful, None otherwise
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_teams (guild_id, team_name, team_tag, created_by, description)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (guild_id, team_name, team_tag, created_by, description))

                    result = cur.fetchone()
                    if result:
                        team_id = result[0]
                        # Automatically add creator as team manager
                        self.add_team_member(team_id, created_by, role='manager')
                        print(f"✅ Created team: {team_name} (ID: {team_id})")
                        return team_id
                    return None
        except Exception as e:
            print(f"❌ Error creating team: {e}")
            return None

    def add_team_member(self, team_id: int, discord_user_id: int, role: str = 'driver', notes: str = None) -> bool:
        """
        Add a member to a team

        Args:
            team_id: Team ID
            discord_user_id: Discord user ID
            role: Member role (driver, crew_chief, spotter, manager)
            notes: Optional notes

        Returns:
            True if successful
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_team_members (team_id, discord_user_id, role, notes)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (team_id, discord_user_id)
                        DO UPDATE SET role = EXCLUDED.role, is_active = TRUE
                    """, (team_id, discord_user_id, role, notes))
                    print(f"✅ Added user {discord_user_id} to team {team_id}")
                    return True
        except Exception as e:
            print(f"❌ Error adding team member: {e}")
            return False

    def remove_team_member(self, team_id: int, discord_user_id: int) -> bool:
        """Remove a member from a team (soft delete)"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE iracing_team_members
                        SET is_active = FALSE
                        WHERE team_id = %s AND discord_user_id = %s
                    """, (team_id, discord_user_id))
                    return True
        except Exception as e:
            print(f"❌ Error removing team member: {e}")
            return False

    def get_user_teams(self, discord_user_id: int, guild_id: int) -> List[Dict]:
        """Get all teams a user is a member of in a specific guild"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT t.id, t.team_name, t.team_tag, tm.role, t.description
                        FROM iracing_teams t
                        JOIN iracing_team_members tm ON t.id = tm.team_id
                        WHERE tm.discord_user_id = %s
                          AND t.guild_id = %s
                          AND t.is_active = TRUE
                          AND tm.is_active = TRUE
                        ORDER BY t.team_name
                    """, (discord_user_id, guild_id))

                    results = cur.fetchall()
                    return [{
                        'id': row[0],
                        'name': row[1],
                        'tag': row[2],
                        'role': row[3],
                        'description': row[4]
                    } for row in results]
        except Exception as e:
            print(f"❌ Error getting user teams: {e}")
            return []

    def get_team_members(self, team_id: int) -> List[Dict]:
        """Get all active members of a team"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT tm.discord_user_id, tm.role, tm.joined_at, tm.notes, il.iracing_name
                        FROM iracing_team_members tm
                        LEFT JOIN iracing_links il ON tm.discord_user_id = il.discord_user_id
                        WHERE tm.team_id = %s AND tm.is_active = TRUE
                        ORDER BY tm.joined_at
                    """, (team_id,))

                    results = cur.fetchall()
                    return [{
                        'discord_user_id': row[0],
                        'role': row[1],
                        'joined_at': row[2],
                        'notes': row[3],
                        'iracing_name': row[4]
                    } for row in results]
        except Exception as e:
            print(f"❌ Error getting team members: {e}")
            return []

    def get_team_info(self, team_id: int) -> Optional[Dict]:
        """Get detailed team information"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, team_name, team_tag, created_by, created_at, description, guild_id
                        FROM iracing_teams
                        WHERE id = %s AND is_active = TRUE
                    """, (team_id,))

                    result = cur.fetchone()
                    if result:
                        return {
                            'id': result[0],
                            'name': result[1],
                            'tag': result[2],
                            'created_by': result[3],
                            'created_at': result[4],
                            'description': result[5],
                            'guild_id': result[6]
                        }
                    return None
        except Exception as e:
            print(f"❌ Error getting team info: {e}")
            return None

    def list_server_teams(self, guild_id: int) -> List[Dict]:
        """List all active teams in a server"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT t.id, t.team_name, t.team_tag, t.created_at, t.description,
                               COUNT(tm.id) as member_count
                        FROM iracing_teams t
                        LEFT JOIN iracing_team_members tm ON t.id = tm.team_id AND tm.is_active = TRUE
                        WHERE t.guild_id = %s AND t.is_active = TRUE
                        GROUP BY t.id
                        ORDER BY t.team_name
                    """, (guild_id,))

                    results = cur.fetchall()
                    return [{
                        'id': row[0],
                        'name': row[1],
                        'tag': row[2],
                        'created_at': row[3],
                        'description': row[4],
                        'member_count': row[5]
                    } for row in results]
        except Exception as e:
            print(f"❌ Error listing server teams: {e}")
            return []

    # ==================== EVENT MANAGEMENT ====================

    def create_event(self, team_id: int, guild_id: int, event_name: str, event_type: str,
                    event_start: datetime, created_by: int, event_duration_minutes: int = None,
                    series_name: str = None, track_name: str = None, notes: str = None) -> Optional[int]:
        """
        Create a team event

        Args:
            team_id: Team ID
            guild_id: Discord server ID
            event_name: Name of the event
            event_type: Type (practice, qualifying, race, endurance)
            event_start: Event start time
            created_by: Discord user ID
            event_duration_minutes: Duration for endurance races
            series_name: Optional series name
            track_name: Optional track name
            notes: Optional notes

        Returns:
            Event ID if successful
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_team_events
                        (team_id, guild_id, event_name, event_type, series_name, track_name,
                         event_start, event_duration_minutes, created_by, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (team_id, guild_id, event_name, event_type, series_name, track_name,
                          event_start, event_duration_minutes, created_by, notes))

                    result = cur.fetchone()
                    if result:
                        event_id = result[0]
                        print(f"✅ Created event: {event_name} (ID: {event_id})")
                        return event_id
                    return None
        except Exception as e:
            print(f"❌ Error creating event: {e}")
            return None

    def get_team_events(self, team_id: int, upcoming_only: bool = True) -> List[Dict]:
        """Get events for a team"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    query = """
                        SELECT id, event_name, event_type, series_name, track_name,
                               event_start, event_duration_minutes, notes, is_cancelled
                        FROM iracing_team_events
                        WHERE team_id = %s
                    """
                    params = [team_id]

                    if upcoming_only:
                        query += " AND event_start > NOW() AND is_cancelled = FALSE"

                    query += " ORDER BY event_start"

                    cur.execute(query, params)
                    results = cur.fetchall()
                    return [{
                        'id': row[0],
                        'name': row[1],
                        'type': row[2],
                        'series': row[3],
                        'track': row[4],
                        'start': row[5],
                        'duration_minutes': row[6],
                        'notes': row[7],
                        'is_cancelled': row[8]
                    } for row in results]
        except Exception as e:
            print(f"❌ Error getting team events: {e}")
            return []

    # ==================== DRIVER AVAILABILITY ====================

    def set_driver_availability(self, event_id: int, discord_user_id: int, status: str,
                               available_from: datetime = None, available_until: datetime = None,
                               notes: str = None) -> bool:
        """
        Set driver availability for an event

        Args:
            event_id: Event ID
            discord_user_id: Discord user ID
            status: available, unavailable, maybe, confirmed
            available_from: For partial availability
            available_until: For partial availability
            notes: Optional notes
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_driver_availability
                        (event_id, discord_user_id, status, available_from, available_until, notes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id, discord_user_id)
                        DO UPDATE SET
                            status = EXCLUDED.status,
                            available_from = EXCLUDED.available_from,
                            available_until = EXCLUDED.available_until,
                            notes = EXCLUDED.notes,
                            updated_at = CURRENT_TIMESTAMP
                    """, (event_id, discord_user_id, status, available_from, available_until, notes))
                    return True
        except Exception as e:
            print(f"❌ Error setting driver availability: {e}")
            return False

    def get_event_availability(self, event_id: int) -> List[Dict]:
        """Get all driver availability for an event"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT da.discord_user_id, da.status, da.available_from, da.available_until,
                               da.notes, da.updated_at, il.iracing_name
                        FROM iracing_driver_availability da
                        LEFT JOIN iracing_links il ON da.discord_user_id = il.discord_user_id
                        WHERE da.event_id = %s
                        ORDER BY da.status, il.iracing_name
                    """, (event_id,))

                    results = cur.fetchall()
                    return [{
                        'discord_user_id': row[0],
                        'status': row[1],
                        'available_from': row[2],
                        'available_until': row[3],
                        'notes': row[4],
                        'updated_at': row[5],
                        'iracing_name': row[6]
                    } for row in results]
        except Exception as e:
            print(f"❌ Error getting event availability: {e}")
            return []

    # ==================== STINT SCHEDULING ====================

    def create_stint(self, event_id: int, discord_user_id: int, stint_number: int,
                    stint_start: datetime, stint_duration_minutes: int,
                    role: str = 'driver', notes: str = None) -> bool:
        """Create a driver stint for an endurance event"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_stint_schedule
                        (event_id, discord_user_id, stint_number, stint_start,
                         stint_duration_minutes, role, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id, stint_number, discord_user_id)
                        DO UPDATE SET
                            stint_start = EXCLUDED.stint_start,
                            stint_duration_minutes = EXCLUDED.stint_duration_minutes,
                            role = EXCLUDED.role,
                            notes = EXCLUDED.notes
                    """, (event_id, discord_user_id, stint_number, stint_start,
                          stint_duration_minutes, role, notes))
                    return True
        except Exception as e:
            print(f"❌ Error creating stint: {e}")
            return False

    def get_stint_schedule(self, event_id: int) -> List[Dict]:
        """Get the complete stint schedule for an event"""
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT ss.stint_number, ss.discord_user_id, ss.stint_start,
                               ss.stint_duration_minutes, ss.role, ss.notes, il.iracing_name
                        FROM iracing_stint_schedule ss
                        LEFT JOIN iracing_links il ON ss.discord_user_id = il.discord_user_id
                        WHERE ss.event_id = %s
                        ORDER BY ss.stint_number
                    """, (event_id,))

                    results = cur.fetchall()
                    return [{
                        'stint_number': row[0],
                        'discord_user_id': row[1],
                        'stint_start': row[2],
                        'duration_minutes': row[3],
                        'role': row[4],
                        'notes': row[5],
                        'iracing_name': row[6]
                    } for row in results]
        except Exception as e:
            print(f"❌ Error getting stint schedule: {e}")
            return []
