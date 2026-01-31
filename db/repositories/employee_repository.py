"""Repository for Employee entity."""
from __future__ import annotations

from datetime import time

from db.connection import Database
from db.repositories.base_repository import BaseRepository
from models import Employee


class EmployeeRepository(BaseRepository[Employee]):
    """Repository for managing employees in the database."""
    
    @property
    def table_name(self) -> str:
        return "employees"
    
    def to_model(self, row: dict) -> Employee:
        """Convert database row to Employee object."""
        # Parse home_location geometry
        home = self.point_from_row(row, "home_location_wkt")
        lat, lon = home if home else (0.0, 0.0)
        
        emp = Employee(
            id=row["id"],
            lat=lat,
            lon=lon,
            name=row.get("full_name"),
        )
        emp.zone_id = row.get("zone_id")
        emp.cluster_id = row.get("cluster_id")
        emp.excluded = row.get("is_excluded", False)
        emp.exclusion_reason = row.get("exclusion_reason", "")
        
        # Parse pickup_point if exists
        pickup = self.point_from_row(row, "pickup_point_wkt")
        if pickup:
            emp.pickup_point = pickup
        emp.pickup_type = row.get("pickup_type", "route")
        
        return emp
    
    def find_all(self, limit: int = 1000) -> list[Employee]:
        """Find all active employees."""
        query = """
            SELECT id, full_name, zone_id, cluster_id, is_excluded, exclusion_reason,
                   pickup_type,
                   ST_AsText(home_location) as home_location_wkt,
                   ST_AsText(pickup_point) as pickup_point_wkt
            FROM employees
            WHERE deleted_at IS NULL
            ORDER BY id
            LIMIT %s
        """
        rows = self.db.fetchall(query, (limit,))
        return [self.to_model(row) for row in rows]
    
    def find_by_id(self, id: int) -> Employee | None:
        """Find employee by ID."""
        query = """
            SELECT id, full_name, zone_id, cluster_id, is_excluded, exclusion_reason,
                   pickup_type,
                   ST_AsText(home_location) as home_location_wkt,
                   ST_AsText(pickup_point) as pickup_point_wkt
            FROM employees
            WHERE id = %s AND deleted_at IS NULL
        """
        row = self.db.fetchone(query, (id,))
        return self.to_model(row) if row else None
    
    def find_by_cluster(self, cluster_id: int) -> list[Employee]:
        """Find all employees in a cluster."""
        query = """
            SELECT id, full_name, zone_id, cluster_id, is_excluded, exclusion_reason,
                   pickup_type,
                   ST_AsText(home_location) as home_location_wkt,
                   ST_AsText(pickup_point) as pickup_point_wkt
            FROM employees
            WHERE cluster_id = %s AND deleted_at IS NULL
            ORDER BY id
        """
        rows = self.db.fetchall(query, (cluster_id,))
        return [self.to_model(row) for row in rows]
    
    def find_by_zone(self, zone_id: int) -> list[Employee]:
        """Find all employees in a zone."""
        query = """
            SELECT id, full_name, zone_id, cluster_id, is_excluded, exclusion_reason,
                   pickup_type,
                   ST_AsText(home_location) as home_location_wkt,
                   ST_AsText(pickup_point) as pickup_point_wkt
            FROM employees
            WHERE zone_id = %s AND deleted_at IS NULL
            ORDER BY id
        """
        rows = self.db.fetchall(query, (zone_id,))
        return [self.to_model(row) for row in rows]
    
    def save(self, employee: Employee) -> int:
        """Insert or update an employee. Returns the ID."""
        home_wkt = self.point_to_wkt(employee.lat, employee.lon)
        pickup_wkt = None
        if employee.pickup_point:
            pickup_wkt = self.point_to_wkt(employee.pickup_point[0], employee.pickup_point[1])
        
        # Check if employee exists
        existing = self.db.fetchone(
            "SELECT id FROM employees WHERE id = %s AND deleted_at IS NULL",
            (employee.id,)
        )
        
        if existing:
            # Update
            query = """
                UPDATE employees SET
                    full_name = %s,
                    home_location = ST_GeomFromText(%s, 4326),
                    zone_id = %s,
                    cluster_id = %s,
                    is_excluded = %s,
                    exclusion_reason = %s,
                    pickup_point = CASE WHEN %s IS NOT NULL THEN ST_GeomFromText(%s, 4326) ELSE NULL END,
                    pickup_type = %s,
                    updated_at = now()
                WHERE id = %s
            """
            self.db.execute(query, (
                employee.name, home_wkt, employee.zone_id, employee.cluster_id,
                employee.excluded, employee.exclusion_reason,
                pickup_wkt, pickup_wkt, employee.pickup_type,
                employee.id
            ))
            return employee.id
        else:
            # Insert
            query = """
                INSERT INTO employees (id, full_name, home_location, zone_id, cluster_id,
                                       is_excluded, exclusion_reason, pickup_point, pickup_type)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s,
                        CASE WHEN %s IS NOT NULL THEN ST_GeomFromText(%s, 4326) ELSE NULL END, %s)
                ON CONFLICT (id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    home_location = EXCLUDED.home_location,
                    zone_id = EXCLUDED.zone_id,
                    cluster_id = EXCLUDED.cluster_id,
                    is_excluded = EXCLUDED.is_excluded,
                    exclusion_reason = EXCLUDED.exclusion_reason,
                    pickup_point = EXCLUDED.pickup_point,
                    pickup_type = EXCLUDED.pickup_type,
                    updated_at = now(),
                    deleted_at = NULL
                RETURNING id
            """
            return self.db.fetchval(query, (
                employee.id, employee.name, home_wkt, employee.zone_id, employee.cluster_id,
                employee.excluded, employee.exclusion_reason,
                pickup_wkt, pickup_wkt, employee.pickup_type
            ))
    
    def save_batch(self, employees: list[Employee]) -> int:
        """Bulk save employees. Returns count of saved employees."""
        count = 0
        for emp in employees:
            self.save(emp)
            count += 1
        return count
    
    def update_cluster_assignment(self, employee_id: int, cluster_id: int | None) -> bool:
        """Update employee's cluster assignment."""
        query = """
            UPDATE employees SET cluster_id = %s, updated_at = now()
            WHERE id = %s AND deleted_at IS NULL
        """
        self.db.execute(query, (cluster_id, employee_id))
        return True
    
    def update_zone_assignment(self, employee_id: int, zone_id: int | None) -> bool:
        """Update employee's zone assignment."""
        query = """
            UPDATE employees SET zone_id = %s, updated_at = now()
            WHERE id = %s AND deleted_at IS NULL
        """
        self.db.execute(query, (zone_id, employee_id))
        return True
    
    def clear_all_clusters(self) -> int:
        """Clear all cluster assignments. Returns count of updated employees."""
        query = "UPDATE employees SET cluster_id = NULL, updated_at = now() WHERE deleted_at IS NULL"
        self.db.execute(query)
        return self.count()
    
    def delete_all(self) -> int:
        """Soft delete all employees."""
        query = "UPDATE employees SET deleted_at = now() WHERE deleted_at IS NULL"
        self.db.execute(query)
        return 0
