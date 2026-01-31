"""Repository for Zone entity."""
from __future__ import annotations

from db.connection import Database
from db.repositories.base_repository import BaseRepository


class Zone:
    """Simple Zone data class for database representation."""
    
    def __init__(self, id: int, name: str, boundary: str | None = None) -> None:
        self.id = id
        self.name = name
        self.boundary = boundary


class ZoneRepository(BaseRepository[Zone]):
    """Repository for managing zones in the database."""
    
    @property
    def table_name(self) -> str:
        return "zones"
    
    def to_model(self, row: dict) -> Zone:
        """Convert database row to Zone object."""
        return Zone(
            id=row["id"],
            name=row.get("name", ""),
            boundary=row.get("boundary_wkt"),
        )
    
    def find_all(self, limit: int = 1000) -> list[Zone]:
        """Find all active zones."""
        query = """
            SELECT id, name, ST_AsText(boundary) as boundary_wkt
            FROM zones
            WHERE deleted_at IS NULL
            ORDER BY id
            LIMIT %s
        """
        rows = self.db.fetchall(query, (limit,))
        return [self.to_model(row) for row in rows]
    
    def find_by_id(self, id: int) -> Zone | None:
        """Find zone by ID."""
        query = """
            SELECT id, name, ST_AsText(boundary) as boundary_wkt
            FROM zones
            WHERE id = %s AND deleted_at IS NULL
        """
        row = self.db.fetchone(query, (id,))
        return self.to_model(row) if row else None
    
    def save(self, name: str, boundary_wkt: str | None = None) -> int:
        """Insert a new zone and return its ID."""
        if boundary_wkt:
            query = """
                INSERT INTO zones (name, boundary)
                VALUES (%s, ST_GeomFromText(%s, 4326))
                RETURNING id
            """
            return self.db.fetchval(query, (name, boundary_wkt))
        else:
            query = """
                INSERT INTO zones (name)
                VALUES (%s)
                RETURNING id
            """
            return self.db.fetchval(query, (name,))
    
    def update(self, id: int, name: str | None = None, boundary_wkt: str | None = None) -> bool:
        """Update zone by ID."""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if boundary_wkt is not None:
            updates.append("boundary = ST_GeomFromText(%s, 4326)")
            params.append(boundary_wkt)
        
        if not updates:
            return False
        
        params.append(id)
        query = f"""
            UPDATE zones SET {", ".join(updates)}, updated_at = now()
            WHERE id = %s AND deleted_at IS NULL
        """
        self.db.execute(query, tuple(params))
        return True
    
    def find_containing_point(self, lat: float, lon: float) -> Zone | None:
        """Find zone that contains the given point."""
        query = """
            SELECT id, name, ST_AsText(boundary) as boundary_wkt
            FROM zones
            WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            AND deleted_at IS NULL
            LIMIT 1
        """
        row = self.db.fetchone(query, (lon, lat))
        return self.to_model(row) if row else None
    
    def delete_all(self) -> int:
        """Soft delete all zones. Returns count of deleted zones."""
        query = "UPDATE zones SET deleted_at = now() WHERE deleted_at IS NULL"
        self.db.execute(query)
        return self.count()
