"""Repository for Vehicle entity."""
from __future__ import annotations

from datetime import datetime

from db.connection import Database
from db.repositories.base_repository import BaseRepository
from models import Vehicle


class VehicleRepository(BaseRepository[Vehicle]):
    """Repository for managing vehicles in the database."""
    
    @property
    def table_name(self) -> str:
        return "vehicles"
    
    def to_model(self, row: dict) -> Vehicle:
        """Convert database row to Vehicle object."""
        vehicle = Vehicle(
            id=row["id"],
            capacity=row.get("capacity", 17),
            vehicle_type=row.get("vehicle_type", "Minibus"),
        )
        vehicle.driver_name = row.get("driver_name")
        return vehicle
    
    def find_all(self, limit: int = 1000) -> list[Vehicle]:
        """Find all active vehicles."""
        query = """
            SELECT id, plate_number, driver_name, driver_phone, capacity, vehicle_type, status
            FROM vehicles
            WHERE deleted_at IS NULL
            ORDER BY id
            LIMIT %s
        """
        rows = self.db.fetchall(query, (limit,))
        return [self.to_model(row) for row in rows]
    
    def find_by_id(self, id: int) -> Vehicle | None:
        """Find vehicle by ID."""
        query = """
            SELECT id, plate_number, driver_name, driver_phone, capacity, vehicle_type, status
            FROM vehicles
            WHERE id = %s AND deleted_at IS NULL
        """
        row = self.db.fetchone(query, (id,))
        return self.to_model(row) if row else None
    

    
    def save(self, vehicle: Vehicle, plate_number: str = None, 
             driver_phone: str = None, status: str = "available") -> int:
        """Insert or update a vehicle. Returns the ID."""
        # Check if vehicle exists
        existing = self.db.fetchone(
            "SELECT id FROM vehicles WHERE id = %s AND deleted_at IS NULL",
            (vehicle.id,)
        )
        
        if existing:
            # Update
            query = """
                UPDATE vehicles SET
                    plate_number = COALESCE(%s, plate_number),
                    driver_name = COALESCE(%s, driver_name),
                    driver_phone = COALESCE(%s, driver_phone),
                    capacity = %s,
                    vehicle_type = %s,
                    status = %s,
                    updated_at = now()
                WHERE id = %s
            """
            self.db.execute(query, (
                plate_number, vehicle.driver_name, driver_phone,
                vehicle.capacity, vehicle.vehicle_type, status,
                vehicle.id
            ))
            return vehicle.id
        else:
            # Insert
            query = """
                INSERT INTO vehicles (plate_number, driver_name, driver_phone, capacity, vehicle_type, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            vehicle_id = self.db.fetchval(query, (
                plate_number or f"PLATE-{vehicle.id}",
                vehicle.driver_name,
                driver_phone,
                vehicle.capacity,
                vehicle.vehicle_type,
                status
            ))
            vehicle.id = vehicle_id
            return vehicle_id
    

    
    def save_batch(self, vehicles: list[Vehicle]) -> list[int]:
        """Bulk save vehicles. Returns list of IDs."""
        ids = []
        for vehicle in vehicles:
            ids.append(self.save(vehicle))
        return ids
