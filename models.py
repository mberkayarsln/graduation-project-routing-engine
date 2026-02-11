"""
Domain models for the route optimization system.

Contains: Employee, Cluster, Route, Vehicle
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from shapely.geometry import Point, LineString, MultiPoint
from shapely.ops import nearest_points

if TYPE_CHECKING:
    pass


from utils import haversine


# =============================================================================
# Employee
# =============================================================================

class Employee:
    """Represents an employee with geographic location and pickup assignment."""
    
    def __init__(self, id: int, lat: float, lon: float, name: str | None = None) -> None:
        self.id = id
        self.lat = lat
        self.lon = lon
        self.name = name or f"Employee {id}"
        self.cluster_id: int | None = None
        self.zone_id: int | None = None
        self.excluded: bool = False
        self.exclusion_reason: str = ""
        self.pickup_point: tuple[float, float] | None = None
        self.walking_distance: float | None = None  # Distance to pickup point in meters
    
    def set_pickup_point(self, lat: float, lon: float, type: str = None, walking_distance: float = None) -> None:
        self.pickup_point = (lat, lon)
        self.walking_distance = walking_distance
    
    def distance_to(self, other_lat: float, other_lon: float) -> float:
        return haversine(self.lat, self.lon, other_lat, other_lon)
    
    def exclude(self, reason: str) -> None:
        self.excluded = True
        self.exclusion_reason = reason
    
    def get_location(self) -> tuple[float, float]:
        return (self.lat, self.lon)
    
    def to_dict(self) -> dict:
        return {
            'id': self.id, 'lat': self.lat, 'lon': self.lon, 'name': self.name,
            'cluster_id': self.cluster_id, 'zone_id': self.zone_id,
            'excluded': self.excluded, 'exclusion_reason': self.exclusion_reason
        }
    
    def __repr__(self) -> str:
        status = "excluded" if self.excluded else f"cluster {self.cluster_id}"
        return f"Employee(id={self.id}, {status})"


# =============================================================================
# Cluster
# =============================================================================

class Cluster:
    """A cluster of employees that share a common pickup route."""
    
    def __init__(self, id: int, center: tuple[float, float]) -> None:
        self.id = id
        self.center = center
        self.original_center: tuple[float, float] | None = None
        self.employees: list[Employee] = []
        self.route: Route | None = None
        self.vehicle: Vehicle | None = None
        self.zone_id: int | None = None
        self.parent_cluster_id: int | None = None
        self.stops: list[tuple[float, float]] = []
        self.stop_assignments: dict[int, int] = {}
        self.stop_loads: list[int] = []
    
    def add_employee(self, employee: Employee) -> None:
        self.employees.append(employee)
        employee.cluster_id = self.id
    
    def filter_by_distance(self, max_distance: float) -> int:
        excluded_count = 0
        center_lat, center_lon = self.center
        for employee in self.employees:
            if employee.distance_to(center_lat, center_lon) > max_distance:
                employee.exclude(f"Too far from center")
                excluded_count += 1
        return excluded_count
    
    def get_active_employees(self) -> list[Employee]:
        return [emp for emp in self.employees if not emp.excluded]
    
    def get_employee_count(self, include_excluded: bool = False) -> int:
        return len(self.employees) if include_excluded else len(self.get_active_employees())
    
    def get_employee_locations(self, include_excluded: bool = False) -> list[tuple[float, float]]:
        employees = self.employees if include_excluded else self.get_active_employees()
        return [emp.get_location() for emp in employees]
    
    def assign_route(self, route: Route) -> None:
        self.route = route
        route.cluster = self
    
    def assign_vehicle(self, vehicle: Vehicle) -> None:
        self.vehicle = vehicle
        vehicle.cluster = self
    
    def set_stops(self, stops: list, assignments: list, stop_loads: list) -> None:
        self.stops = stops
        self.stop_loads = stop_loads
        self.stop_assignments = {}
        for i, employee in enumerate(self.get_active_employees()):
            if i < len(assignments):
                self.stop_assignments[employee.id] = assignments[i]
    
    def get_employee_stop(self, employee: Employee) -> tuple[int | None, tuple | None]:
        if employee.id in self.stop_assignments:
            idx = self.stop_assignments[employee.id]
            if idx < len(self.stops):
                return idx, self.stops[idx]
        return None, None
    
    def has_stops(self) -> bool:
        return len(self.stops) > 0
    
    def get_stats(self) -> dict:
        active = self.get_employee_count(include_excluded=False)
        total = self.get_employee_count(include_excluded=True)
        stats = {
            'id': self.id, 'center': self.center, 'total_employees': total,
            'active_employees': active, 'excluded_employees': total - active,
            'has_route': self.route is not None, 'n_stops': len(self.stops)
        }
        if self.route:
            stats['route_distance_km'] = self.route.distance_km
        return stats
    
    def __repr__(self) -> str:
        return f"Cluster(id={self.id}, employees={len(self.employees)})"


# =============================================================================
# Route
# =============================================================================

class Route:
    """An optimized route for a cluster with stops and distance/duration info."""
    
    def __init__(self, cluster: Cluster | None = None) -> None:
        self.cluster = cluster
        self.stops: list[tuple[float, float]] = []
        self.bus_stops: list[tuple[float, float]] = []  # All bus stops along the route
        self.coordinates: list[list[float]] = []
        self.distance_km: float = 0.0
        self.duration_min: float = 0.0
        self.duration_no_traffic_min: float = 0.0
        self.traffic_delay_min: float = 0.0
        self.optimized: bool = False
        self.has_traffic_data: bool = False
    
    def set_stops(self, stops: list) -> None:
        self.stops = stops
    
    def set_coordinates(self, coordinates: list) -> None:
        self.coordinates = coordinates
    
    def add_stop(self, lat: float, lon: float) -> None:
        self.stops.append((lat, lon))
    
    def set_distance(self, distance_km: float) -> None:
        self.distance_km = distance_km
    
    def set_duration(self, duration_min: float, no_traffic_min: float | None = None) -> None:
        self.duration_min = duration_min
        if no_traffic_min:
            self.duration_no_traffic_min = no_traffic_min
            self.traffic_delay_min = duration_min - no_traffic_min
            self.has_traffic_data = True
    
    def set_traffic_data(self, traffic_info: dict) -> None:
        self.coordinates = traffic_info.get('coordinates', [])
        self.distance_km = traffic_info.get('distance_km', 0)
        self.duration_min = traffic_info.get('duration_with_traffic_min', 0)
        self.duration_no_traffic_min = traffic_info.get('duration_no_traffic_min', 0)
        self.traffic_delay_min = traffic_info.get('traffic_delay_min', 0)
        self.has_traffic_data = True
    
    def mark_optimized(self) -> None:
        self.optimized = True
    
    def get_stop_count(self) -> int:
        return len(self.stops)
    
    def get_avg_speed_kmh(self) -> float:
        return (self.distance_km / self.duration_min) * 60 if self.duration_min > 0 else 0
    
    def calculate_stats_from_stops(self) -> None:
        if not self.stops or len(self.stops) < 2:
            self.distance_km = self.duration_min = 0
            return
        total = sum(haversine(*self.stops[i], *self.stops[i+1]) for i in range(len(self.stops)-1))
        self.distance_km = total / 1000
        self.duration_min = (self.distance_km / 40) * 60
    
    def get_stats(self) -> dict:
        return {
            'stops': len(self.stops), 'distance_km': round(self.distance_km, 2),
            'duration_min': round(self.duration_min, 1), 'optimized': self.optimized
        }
    
    def to_dict(self) -> dict:
        return {
            'coordinates': self.coordinates or self.stops, 'stops': self.stops,
            'bus_stops': self.bus_stops,
            'distance_km': self.distance_km, 'duration_min': self.duration_min
        }
    
    def find_all_stops_along_route(
        self,
        all_stops: list,
        buffer_meters: float = 150,
        same_side_only: bool = True
    ) -> list[tuple[float, float]]:
        """Find ALL bus stops within buffer_meters of the route path.
        
        Args:
            all_stops: List of (lat, lon) tuples of all known bus stops.
            buffer_meters: Search buffer in meters (default 150m).
            same_side_only: If True, only include stops on the right side of the route.
        
        Returns:
            List of (lat, lon) tuples of bus stops along the route, ordered by position on route.
        """
        if not self.coordinates or len(self.coordinates) < 2:
            return []
        
        try:
            line = LineString(self.coordinates)
            # Convert buffer from meters to approximate degrees
            # ~1 degree lat ≈ 111,000m; at Istanbul's latitude ~1 degree lon ≈ 85,000m
            buffer_deg = buffer_meters / 111_000  # conservative estimate
            
            found_stops = []
            for s in all_stops:
                s_point = Point(s[0], s[1])
                if line.distance(s_point) < buffer_deg:
                    # Store with position along route for ordering
                    pos = line.project(s_point)
                    
                    # Filter by side if requested
                    if same_side_only:
                        delta = 1e-5
                        p1 = line.interpolate(max(0, pos - delta))
                        p2 = line.interpolate(min(line.length, pos + delta))
                        
                        vx = p2.x - p1.x
                        vy = p2.y - p1.y
                        wx = s_point.x - p1.x
                        wy = s_point.y - p1.y
                        
                        cross_product = vx * wy - vy * wx
                        
                        # Only include if on the right side (cross product >= 0)
                        if cross_product < -1e-10:
                            continue
                    
                    found_stops.append((pos, s))
            
            # Sort by position along the route
            found_stops.sort(key=lambda x: x[0])
            self.bus_stops = [s for _, s in found_stops]
            return self.bus_stops
        except Exception:
            return []

    def match_employees_to_route(
        self,
        employees: list[Employee],
        safe_stops: list | None = None,
        buffer_meters: float = 150,
    ) -> int:
        """Match employees to pickup points along the route."""
        if not self.coordinates or len(self.coordinates) < 2:
            return 0
        
        try:
            line = LineString(self.coordinates)
            matched_count = 0
            
            valid_route_stops = [s for s in self.stops] if self.stops else []
            
            # Add safe stops near the route (within buffer_meters of route)
            buffer_deg = buffer_meters / 111_000  # meters -> degrees (approx)
            if safe_stops and len(safe_stops) > 0:
                for s in safe_stops:
                    s_point = Point(s[0], s[1])
                    if line.distance(s_point) < buffer_deg:
                        valid_route_stops.append(s)
            
            # Filter stops to only those on the right side of the route
            if valid_route_stops:
                filtered_stops = []
                for s in valid_route_stops:
                    s_point = Point(s[0], s[1])
                    dist = line.project(s_point)
                    
                    delta = 1e-5
                    p1 = line.interpolate(max(0, dist - delta))
                    p2 = line.interpolate(min(line.length, dist + delta))
                    
                    vx = p2.x - p1.x
                    vy = p2.y - p1.y
                    wx = s_point.x - p1.x
                    wy = s_point.y - p1.y
                    
                    cross_product = vx * wy - vy * wx
                    
                    if cross_product >= -1e-10:
                        filtered_stops.append(s)
                
                valid_route_stops = filtered_stops
            
            # Match employees to stops using OSRM distance matrix
            if valid_route_stops:
                active_employees = [e for e in employees if not e.excluded]
                
                if not active_employees:
                    return 0
                    
                from routing import OSRMRouter
                router = OSRMRouter()
                
                emp_locs = [(e.lat, e.lon) for e in active_employees]
                distances_matrix = router.get_distance_matrix(emp_locs, valid_route_stops, profile='foot')
                
                if distances_matrix:
                    for i, employee in enumerate(active_employees):
                        dists = distances_matrix[i]
                        
                        min_dist_meters = float('inf')
                        best_stop_idx = -1
                        
                        for stop_idx, dist in enumerate(dists):
                            if dist is not None and dist < min_dist_meters:
                                min_dist_meters = dist
                                best_stop_idx = stop_idx
                        
                        if best_stop_idx != -1:
                            best_stop = valid_route_stops[best_stop_idx]
                            employee.set_pickup_point(best_stop[0], best_stop[1], type="stop", walking_distance=min_dist_meters)
                            matched_count += 1
                    
                    return matched_count
            
            # Only use real bus stops from safe_stops - no custom pickup point generation
            if not valid_route_stops:
                return 0
            
            valid_stops_multipoint = None
            try:
                valid_stops_multipoint = MultiPoint([(s[0], s[1]) for s in valid_route_stops])
            except Exception:
                return 0
            
            for employee in employees:
                if employee.excluded:
                    continue
                
                emp_point = Point(employee.lat, employee.lon)
                
                # Only assign to real bus stops, not projected points on the route
                if valid_stops_multipoint:
                    nearest_stop = nearest_points(emp_point, valid_stops_multipoint)[1]
                    employee.set_pickup_point(nearest_stop.x, nearest_stop.y, type="stop")
                    matched_count += 1
                
            return matched_count
            
        except ImportError:
            return 0
        except Exception:
            return 0

    def __repr__(self) -> str:
        return f"Route(stops={len(self.stops)}, distance={self.distance_km:.1f}km)"


# =============================================================================
# Vehicle
# =============================================================================

class Vehicle:
    """A service vehicle with capacity and route assignment."""
    
    def __init__(self, id: int, capacity: int = 50, vehicle_type: str = "Minibus") -> None:
        self.id = id
        self.capacity = capacity
        self.vehicle_type = vehicle_type
        self.cluster: Cluster | None = None
        self.route: Route | None = None
        self.departure_time: datetime | None = None
        self.driver_name: str | None = None
    
    def assign_cluster(self, cluster: Cluster) -> None:
        self.cluster = cluster
        self.route = cluster.route if cluster else None
    
    def set_departure_time(self, departure_time: datetime) -> None:
        self.departure_time = departure_time
    
    def can_accommodate(self, employee_count: int) -> bool:
        return employee_count <= self.capacity
    
    def get_occupancy_rate(self) -> float:
        if self.cluster:
            return (self.cluster.get_employee_count() / self.capacity) * 100
        return 0
    
    def is_full(self) -> bool:
        return self.get_occupancy_rate() >= 100
    
    def get_stats(self) -> dict:
        stats = {
            'id': self.id, 'type': self.vehicle_type, 'capacity': self.capacity,
            'occupancy_rate': round(self.get_occupancy_rate(), 1)
        }
        if self.cluster:
            stats['cluster_id'] = self.cluster.id
        if self.route:
            stats['route_distance_km'] = self.route.distance_km
        return stats
    
    def __repr__(self) -> str:
        return f"Vehicle(id={self.id}, capacity={self.capacity})"
