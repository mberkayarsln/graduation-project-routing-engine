"""Repository for Vehicle entity."""
from __future__ import annotations

from datetime import date, datetime

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
    
    def find_available(self) -> list[Vehicle]:
        """Find all available vehicles."""
        query = """
            SELECT id, plate_number, driver_name, driver_phone, capacity, vehicle_type, status
            FROM vehicles
            WHERE status = 'available' AND deleted_at IS NULL
            ORDER BY id
        """
        rows = self.db.fetchall(query)
        return [self.to_model(row) for row in rows]
    
    def find_by_capacity(self, min_capacity: int) -> list[Vehicle]:
        """Find vehicles with at least the specified capacity."""
        query = """
            SELECT id, plate_number, driver_name, driver_phone, capacity, vehicle_type, status
            FROM vehicles
            WHERE capacity >= %s AND status = 'available' AND deleted_at IS NULL
            ORDER BY capacity
        """
        rows = self.db.fetchall(query, (min_capacity,))
        return [self.to_model(row) for row in rows]
    
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
    
    def update_status(self, vehicle_id: int, status: str) -> bool:
        """Update vehicle status."""
        valid_statuses = ["available", "in_service", "maintenance", "inactive"]
        if status not in valid_statuses:
            return False
        
        query = """
            UPDATE vehicles SET status = %s, updated_at = now()
            WHERE id = %s AND deleted_at IS NULL
        """
        self.db.execute(query, (status, vehicle_id))
        return True
    
    def assign_to_route(self, vehicle_id: int, route_id: int, 
                        assigned_date: date | None = None) -> int:
        """Create a vehicle assignment for a route. Returns assignment ID."""
        if assigned_date is None:
            assigned_date = date.today()
        
        # Check for existing assignment
        existing = self.db.fetchone(
            """SELECT id FROM vehicle_assignments 
               WHERE vehicle_id = %s AND route_id = %s AND assigned_date = %s""",
            (vehicle_id, route_id, assigned_date)
        )
        
        if existing:
            return existing["id"]
        
        query = """
            INSERT INTO vehicle_assignments (vehicle_id, route_id, assigned_date, is_active)
            VALUES (%s, %s, %s, true)
            RETURNING id
        """
        return self.db.fetchval(query, (vehicle_id, route_id, assigned_date))
    
    def get_assignments(self, vehicle_id: int, from_date: date | None = None) -> list[dict]:
        """Get vehicle assignments."""
        if from_date is None:
            from_date = date.today()
        
        query = """
            SELECT va.id, va.route_id, va.assigned_date, va.is_active,
                   r.cluster_id, r.distance_km, r.duration_min
            FROM vehicle_assignments va
            JOIN routes r ON r.id = va.route_id
            WHERE va.vehicle_id = %s AND va.assigned_date >= %s
            ORDER BY va.assigned_date
        """
        return self.db.fetchall(query, (vehicle_id, from_date))
    
    def save_batch(self, vehicles: list[Vehicle]) -> list[int]:
        """Bulk save vehicles. Returns list of IDs."""
        ids = []
        for vehicle in vehicles:
            ids.append(self.save(vehicle))
        return ids
