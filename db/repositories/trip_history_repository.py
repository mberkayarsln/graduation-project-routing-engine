"""Repository for Trip History entity."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from db.connection import Database


class TripHistoryRepository:
    """Repository for managing trip history records in the database."""

    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()

    # =========================================================================
    # Create
    # =========================================================================

    def save_trip(
        self,
        route_id: int,
        driver_id: int | None = None,
        driver_name: str | None = None,
        vehicle_id: int | None = None,
        vehicle_plate: str | None = None,
        distance_km: float = 0,
        duration_min: int = 0,
        total_stops: int = 0,
        total_passengers: int = 0,
        boarded_count: int = 0,
        absent_count: int = 0,
        started_at: str | None = None,
        ended_at: str | None = None,
        status: str = "completed",
        passengers: list[dict] | None = None,
    ) -> int:
        """Save a completed trip. Returns the trip ID."""
        query = """
            INSERT INTO trip_history
                (route_id, driver_id, driver_name, vehicle_id, vehicle_plate,
                 distance_km, duration_min, total_stops,
                 total_passengers, boarded_count, absent_count,
                 started_at, ended_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        trip_id = self.db.fetchval(query, (
            route_id, driver_id, driver_name, vehicle_id, vehicle_plate,
            distance_km, duration_min, total_stops,
            total_passengers, boarded_count, absent_count,
            started_at or datetime.utcnow().isoformat(),
            ended_at or datetime.utcnow().isoformat(),
            status,
        ))

        # Save passenger records if provided
        if passengers and trip_id:
            for p in passengers:
                self._save_passenger(trip_id, p)

        return trip_id

    def _save_passenger(self, trip_id: int, passenger: dict) -> None:
        """Insert a single trip-passenger record."""
        query = """
            INSERT INTO trip_passengers (trip_id, employee_id, employee_name, boarding_status)
            VALUES (%s, %s, %s, %s)
        """
        self.db.execute(query, (
            trip_id,
            passenger.get("employee_id"),
            passenger.get("employee_name"),
            passenger.get("boarding_status", "waiting"),
        ))

    # =========================================================================
    # Read — Driver
    # =========================================================================

    def find_by_driver(self, driver_id: int, limit: int = 50) -> list[dict]:
        """Get trip history for a specific driver (most recent first)."""
        query = """
            SELECT id, route_id, driver_name, vehicle_plate,
                   distance_km, duration_min, total_stops,
                   total_passengers, boarded_count, absent_count,
                   started_at, ended_at, status
            FROM trip_history
            WHERE driver_id = %s
            ORDER BY started_at DESC
            LIMIT %s
        """
        return self.db.fetchall(query, (driver_id, limit))

    # =========================================================================
    # Read — Employee
    # =========================================================================

    def find_by_employee(self, employee_id: int, limit: int = 50) -> list[dict]:
        """Get trip history for a specific employee (most recent first)."""
        query = """
            SELECT th.id, th.route_id, th.driver_name, th.vehicle_plate,
                   th.distance_km, th.duration_min, th.total_stops,
                   th.total_passengers, th.boarded_count, th.absent_count,
                   th.started_at, th.ended_at, th.status,
                   tp.boarding_status
            FROM trip_history th
            JOIN trip_passengers tp ON tp.trip_id = th.id
            WHERE tp.employee_id = %s
            ORDER BY th.started_at DESC
            LIMIT %s
        """
        return self.db.fetchall(query, (employee_id, limit))

    # =========================================================================
    # Read — By Route
    # =========================================================================

    def find_by_route(self, route_id: int, limit: int = 50) -> list[dict]:
        """Get trip history for a specific route."""
        query = """
            SELECT id, route_id, driver_name, vehicle_plate,
                   distance_km, duration_min, total_stops,
                   total_passengers, boarded_count, absent_count,
                   started_at, ended_at, status
            FROM trip_history
            WHERE route_id = %s
            ORDER BY started_at DESC
            LIMIT %s
        """
        return self.db.fetchall(query, (route_id, limit))

    # =========================================================================
    # Read — Single trip details
    # =========================================================================

    def find_by_id(self, trip_id: int) -> dict | None:
        """Get a single trip with passenger details."""
        trip = self.db.fetchone("""
            SELECT id, route_id, driver_id, driver_name, vehicle_id, vehicle_plate,
                   distance_km, duration_min, total_stops,
                   total_passengers, boarded_count, absent_count,
                   started_at, ended_at, status
            FROM trip_history
            WHERE id = %s
        """, (trip_id,))
        if not trip:
            return None

        passengers = self.db.fetchall("""
            SELECT employee_id, employee_name, boarding_status
            FROM trip_passengers
            WHERE trip_id = %s
            ORDER BY id
        """, (trip_id,))

        trip["passengers"] = passengers
        return trip
