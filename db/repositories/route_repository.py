"""Repository for Route and RouteStop entities."""
from __future__ import annotations

from db.connection import Database
from db.repositories.base_repository import BaseRepository
from models import Route, Cluster


class RouteRepository(BaseRepository[Route]):
    """Repository for managing routes and route stops in the database."""
    
    @property
    def table_name(self) -> str:
        return "routes"
    
    def to_model(self, row: dict, stops_rows: list[dict] | None = None) -> Route:
        """Convert database row to Route object."""
        route = Route()
        route.distance_km = row.get("distance_km", 0.0)
        route.duration_min = row.get("duration_min", 0.0)
        route.optimized = row.get("is_optimized", False) or row.get("optimization_status") == "optimized"
        
        # Parse path_geometry to coordinates
        coords = self.linestring_from_row(row, "path_geometry_wkt")
        if coords:
            route.coordinates = coords
        
        # Parse stops from stops_rows
        if stops_rows:
            for stop_row in stops_rows:
                stop_loc = self.point_from_row(stop_row, "location_wkt")
                if stop_loc:
                    route.stops.append(stop_loc)
        
        return route
    
    def find_by_id(self, id: int) -> tuple[Route, int, int] | None:
        """Find route by ID. Returns (Route, cluster_id, vehicle_id) or None."""
        query = """
            SELECT id, cluster_id, vehicle_id, distance_km, duration_min,
                   is_optimized, optimization_status,
                   ST_AsText(path_geometry) as path_geometry_wkt
            FROM routes
            WHERE id = %s AND deleted_at IS NULL
        """
        row = self.db.fetchone(query, (id,))
        if not row:
            return None
        
        stops = self._get_stops(id)
        route = self.to_model(row, stops)
        return route, row.get("cluster_id"), row.get("vehicle_id")
    
    def find_by_cluster(self, cluster_id: int) -> Route | None:
        """Find route for a cluster."""
        query = """
            SELECT id, cluster_id, vehicle_id, distance_km, duration_min,
                   is_optimized, optimization_status,
                   ST_AsText(path_geometry) as path_geometry_wkt
            FROM routes
            WHERE cluster_id = %s AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = self.db.fetchone(query, (cluster_id,))
        if not row:
            return None
        
        stops = self._get_stops(row["id"])
        return self.to_model(row, stops)
    
    def _get_stops(self, route_id: int) -> list[dict]:
        """Get all stops for a route."""
        query = """
            SELECT id, stop_sequence, stop_type, estimated_arrival,
                   ST_AsText(location) as location_wkt
            FROM route_stops
            WHERE route_id = %s AND deleted_at IS NULL
            ORDER BY stop_sequence
        """
        return self.db.fetchall(query, (route_id,))
    
    def save(self, route: Route, cluster_id: int, vehicle_id: int | None = None) -> int:
        """Insert or update a route with its stops. Returns route ID."""
        # Build path geometry from coordinates or stops
        path_coords = route.coordinates if route.coordinates else route.stops
        path_wkt = self.linestring_to_wkt(path_coords) if path_coords else None
        
        optimization_status = "optimized" if route.optimized else "pending"
        
        # Check if route exists for this cluster
        existing = self.db.fetchone(
            "SELECT id FROM routes WHERE cluster_id = %s AND deleted_at IS NULL",
            (cluster_id,)
        )
        
        if existing:
            # Update existing route
            route_id = existing["id"]
            query = """
                UPDATE routes SET
                    vehicle_id = %s,
                    distance_km = %s,
                    duration_min = %s,
                    path_geometry = CASE WHEN %s IS NOT NULL THEN ST_GeomFromText(%s, 4326) ELSE path_geometry END,
                    is_optimized = %s,
                    optimization_status = %s,
                    updated_at = now()
                WHERE id = %s
            """
            self.db.execute(query, (
                vehicle_id, route.distance_km, route.duration_min,
                path_wkt, path_wkt,
                route.optimized, optimization_status,
                route_id
            ))
        else:
            # Insert new route
            query = """
                INSERT INTO routes (cluster_id, vehicle_id, distance_km, duration_min,
                                   path_geometry, is_optimized, optimization_status)
                VALUES (%s, %s, %s, %s,
                        CASE WHEN %s IS NOT NULL THEN ST_GeomFromText(%s, 4326) ELSE NULL END,
                        %s, %s)
                RETURNING id
            """
            route_id = self.db.fetchval(query, (
                cluster_id, vehicle_id, route.distance_km, route.duration_min,
                path_wkt, path_wkt,
                route.optimized, optimization_status
            ))
        
        # Save stops
        if route.stops:
            self._save_stops(route_id, route.stops)
        
        return route_id
    
    def _save_stops(self, route_id: int, stops: list[tuple[float, float]]) -> None:
        """Save route stops, replacing existing ones."""
        # Delete existing stops
        self.db.execute(
            "DELETE FROM route_stops WHERE route_id = %s",
            (route_id,)
        )
        
        # Insert new stops
        for seq, (lat, lon) in enumerate(stops):
            stop_wkt = self.point_to_wkt(lat, lon)
            stop_type = "pickup"
            if seq == len(stops) - 1:
                stop_type = "destination"
            elif seq == 0:
                stop_type = "origin"
            
            query = """
                INSERT INTO route_stops (route_id, stop_sequence, location, stop_type)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s)
            """
            self.db.execute(query, (route_id, seq, stop_wkt, stop_type))
    

    
    def delete_all(self) -> int:
        """Soft delete all routes and their stops."""
        self.db.execute("UPDATE route_stops SET deleted_at = now() WHERE deleted_at IS NULL")
        self.db.execute("UPDATE routes SET deleted_at = now() WHERE deleted_at IS NULL")
        return 0
