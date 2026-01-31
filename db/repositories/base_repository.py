"""Base repository with common CRUD patterns."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic

from db.connection import Database


T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Abstract base class for all repositories."""
    
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database()
    
    @property
    @abstractmethod
    def table_name(self) -> str:
        """Return the table name for this repository."""
        pass
    
    @abstractmethod
    def to_model(self, row: dict) -> T:
        """Convert a database row to a domain model."""
        pass
    
    def find_by_id(self, id: int) -> T | None:
        """Find a record by ID."""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE id = %s AND deleted_at IS NULL
        """
        row = self.db.fetchone(query, (id,))
        return self.to_model(row) if row else None
    
    def find_all(self, limit: int = 1000) -> list[T]:
        """Find all active records."""
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE deleted_at IS NULL
            ORDER BY id
            LIMIT %s
        """
        rows = self.db.fetchall(query, (limit,))
        return [self.to_model(row) for row in rows]
    
    def delete(self, id: int) -> bool:
        """Soft delete a record."""
        query = f"""
            UPDATE {self.table_name}
            SET deleted_at = now()
            WHERE id = %s AND deleted_at IS NULL
        """
        self.db.execute(query, (id,))
        return True
    
    def hard_delete(self, id: int) -> bool:
        """Permanently delete a record."""
        query = f"DELETE FROM {self.table_name} WHERE id = %s"
        self.db.execute(query, (id,))
        return True
    
    def count(self) -> int:
        """Count all active records."""
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE deleted_at IS NULL"
        return self.db.fetchval(query) or 0
    
    # =========================================================================
    # Geometry Helpers
    # =========================================================================
    
    @staticmethod
    def point_to_wkt(lat: float, lon: float) -> str:
        """Convert lat/lon to WKT POINT (PostGIS uses lon, lat order)."""
        return f"POINT({lon} {lat})"
    
    @staticmethod
    def point_from_row(row: dict, column: str) -> tuple[float, float] | None:
        """Extract lat/lon tuple from a geometry column."""
        if row.get(column) is None:
            return None
        # When using ST_AsText, we get 'POINT(lon lat)'
        geom = row[column]
        if isinstance(geom, str) and geom.startswith("POINT"):
            coords = geom.replace("POINT(", "").replace(")", "").split()
            return (float(coords[1]), float(coords[0]))  # Return as (lat, lon)
        return None
    
    @staticmethod
    def linestring_to_wkt(coordinates: list[tuple[float, float]]) -> str:
        """Convert list of (lat, lon) to WKT LINESTRING."""
        if not coordinates:
            return None
        points = ", ".join([f"{lon} {lat}" for lat, lon in coordinates])
        return f"LINESTRING({points})"
    
    @staticmethod
    def linestring_from_row(row: dict, column: str) -> list[tuple[float, float]] | None:
        """Extract coordinates list from a LINESTRING geometry column."""
        if row.get(column) is None:
            return None
        geom = row[column]
        if isinstance(geom, str) and geom.startswith("LINESTRING"):
            coords_str = geom.replace("LINESTRING(", "").replace(")", "")
            coords = []
            for point in coords_str.split(","):
                lon, lat = point.strip().split()
                coords.append((float(lat), float(lon)))
            return coords
        return None
