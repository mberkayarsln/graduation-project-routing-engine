"""
Service classes for the route optimization system.

Contains: LocationService, ClusteringService, RoutingService, 
          VisualizationService, ZoneService, ServicePlanner
"""
from __future__ import annotations

import hashlib
import math
import os
import random
from datetime import datetime, timedelta

import folium
import numpy as np
from shapely.geometry import Point, box, MultiLineString, LineString
from shapely.ops import unary_union, polygonize
from pyrosm import OSM

from models import Employee, Cluster, Route, Vehicle
from utils import DataGenerator, KMeansClusterer
from routing import OSRMRouter


# =============================================================================
# Location Service
# =============================================================================

class LocationService:
    """Service for generating and managing employee locations."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.data_generator = DataGenerator()
    
    def generate_employees(self, count: int, seed: int | None = None) -> list[Employee]:
        df = self.data_generator.generate(n=count, seed=seed)
        return [Employee(id=int(row['id']), lat=row['lat'], lon=row['lon']) 
                for _, row in df.iterrows()]
    
    def get_transit_stops(self) -> list[tuple[float, float]]:
        return self.data_generator.get_transit_stops()


# =============================================================================
# Clustering Service
# =============================================================================

class ClusteringService:
    """Service for clustering employees into groups."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.clusterer: KMeansClusterer | None = None
    
    def cluster_employees(self, employees: list[Employee], num_clusters: int, random_state: int | None = None) -> list[Cluster]:
        self.clusterer = KMeansClusterer(n_clusters=num_clusters, random_state=random_state)
        coords = np.array([[e.lat, e.lon] for e in employees])
        self.clusterer.fit(coords)
        
        clusters = [Cluster(id=i, center=tuple(self.clusterer.cluster_centers_[i])) 
                    for i in range(num_clusters)]
        for emp, cid in zip(employees, self.clusterer.labels_):
            clusters[cid].add_employee(emp)
        return clusters
    
    def cluster_by_zones(self, zone_assignments: dict, employees_per_cluster: int = 20, random_state: int | None = None) -> list[Cluster]:
        clusters = []
        gid = 0
        
        for zone_id, zone_emps in zone_assignments.items():
            if not zone_emps:
                continue
            n = len(zone_emps)
            n_clusters = max(1, min(n, math.ceil(n / employees_per_cluster)))

            
            if n_clusters == 1:
                center = (sum(e.lat for e in zone_emps)/n, sum(e.lon for e in zone_emps)/n)
                c = Cluster(id=gid, center=center)
                c.zone_id = zone_id
                for e in zone_emps:
                    c.add_employee(e)
                clusters.append(c)
                gid += 1
            else:
                km = KMeansClusterer(n_clusters=n_clusters, random_state=random_state)
                km.fit(np.array([[e.lat, e.lon] for e in zone_emps]))
                zone_clusters = []
                for i in range(n_clusters):
                    c = Cluster(id=gid, center=tuple(km.cluster_centers_[i]))
                    c.zone_id = zone_id
                    zone_clusters.append(c)
                    gid += 1
                for emp, idx in zip(zone_emps, km.labels_):
                    zone_clusters[idx].add_employee(emp)
                clusters.extend(zone_clusters)
        return clusters
    
    def snap_centers_to_roads(self, clusters: list[Cluster]) -> int:
        router = OSRMRouter()
        count = 0
        for c in clusters:
            result = router.snap_to_road(c.center[0], c.center[1])
            if result:
                c.original_center = c.center
                c.center = (result['lat'], result['lon'])
                count += 1

        return count
    
    def enforce_capacity_constraints(self, clusters: list[Cluster], capacity: int) -> list[Cluster]:
        new_clusters = []
        next_id = max(c.id for c in clusters) + 1
        
        for c in clusters:
            active = c.get_employee_count(include_excluded=False)
            if active <= capacity:
                new_clusters.append(c)
            else:
                n_splits = math.ceil(active / capacity)

                active_emps = c.get_active_employees()
                
                km = KMeansClusterer(n_clusters=n_splits, random_state=42)
                km.fit(np.array([[e.lat, e.lon] for e in active_emps]))
                
                subs = [Cluster(id=next_id+i, center=tuple(km.cluster_centers_[i])) for i in range(n_splits)]
                for s in subs:
                    s.zone_id = getattr(c, 'zone_id', None)
                    s.parent_cluster_id = c.id
                
                for emp, idx in zip(active_emps, km.labels_):
                    subs[idx].add_employee(emp)
                
                for e in c.employees:
                    if e.excluded:
                        nearest = min(subs, key=lambda s: e.distance_to(*s.center))
                        nearest.add_employee(e)
                
                new_clusters.extend(subs)
                next_id += n_splits
        return new_clusters
    
    def validate_capacity(self, clusters: list[Cluster], capacity: int) -> tuple[bool, list]:
        violations = [{'cluster_id': c.id, 'count': c.get_employee_count(False)} 
                      for c in clusters if c.get_employee_count(False) > capacity]
        return len(violations) == 0, violations


# =============================================================================
# Routing Service
# =============================================================================

class RoutingService:
    """Service for optimizing vehicle routes."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.osrm_router = OSRMRouter()
    
    def optimize_cluster_route(self, cluster: Cluster, use_stops: bool = True) -> Route | None:
        stops = cluster.stops if use_stops and cluster.has_stops() else cluster.get_employee_locations(False)

        
        if not stops:
            return None
        
        route = Route(cluster=cluster)
        route.set_stops(stops)
        
        try:
            data = self.osrm_router.get_route(stops)
            route.coordinates = data['coordinates']
            route.distance_km = data['distance_km']
            route.duration_min = data['duration_min']
        except Exception:
            route.calculate_stats_from_stops()
        
        cluster.assign_route(route)
        return route


# =============================================================================
# Visualization Service
# =============================================================================

class VisualizationService:
    """Service for creating map visualizations."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.colors: dict[int, str] = {}
    
    def _color(self, id: int) -> str:
        if id not in self.colors:
            random.seed(int(hashlib.md5(f"c{id}".encode()).hexdigest(), 16))
            h = int((id * 0.618 * 360) % 360 + random.randint(-30, 30)) % 360
            self.colors[id] = f'hsl({h}, {random.randint(65,95)}%, {random.randint(40,70)}%)'
        return self.colors[id]
    
    def create_employees_map(self, employees: list[Employee]) -> str:
        fn = "maps/employees.html"
        if not employees:
            return fn
        m = folium.Map(location=[sum(e.lat for e in employees)/len(employees), 
                                  sum(e.lon for e in employees)/len(employees)], zoom_start=12)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        for e in employees:
            folium.CircleMarker([e.lat, e.lon], radius=4, color='#2563eb', fill=True).add_to(m)
        m.save(fn)
        return fn
    
    def create_clusters_map(self, clusters: list[Cluster]) -> str:
        fn = "maps/clusters.html"
        all_emps = [e for c in clusters for e in c.employees]
        if not all_emps:
            return fn
        m = folium.Map(location=[sum(e.lat for e in all_emps)/len(all_emps), 
                                  sum(e.lon for e in all_emps)/len(all_emps)], zoom_start=12)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        for c in clusters:
            folium.Marker(c.center, popup=f"Cluster {c.id}", icon=folium.Icon(color='black', icon='star', prefix='fa')).add_to(m)
        for e in all_emps:
            folium.CircleMarker([e.lat, e.lon], radius=5, color=self._color(e.cluster_id), fill=True).add_to(m)
        m.save(fn)
        return fn
    
    def create_routes_map(self, clusters: list[Cluster]) -> str:
        fn = "maps/optimized_routes.html"
        m = folium.Map(location=self.office_location, zoom_start=11)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        
        for c in clusters:
            if not c.route:
                continue
            color = self._color(c.id)
            if c.route.coordinates:
                folium.PolyLine(c.route.coordinates, color=color, weight=4, opacity=0.7).add_to(m)
            for e in c.get_active_employees():
                folium.CircleMarker(e.get_location(), radius=3, color=color, fill=True).add_to(m)
            folium.Marker(c.center, icon=folium.DivIcon(html=f'<div style="background:{color};color:white;padding:5px;border-radius:50%;width:30px;height:30px;text-align:center;line-height:30px;font-weight:bold;border:3px solid white">{c.id}</div>')).add_to(m)
        m.save(fn)
        return fn
    
    def create_cluster_detail_map(self, cluster: Cluster) -> str:
        os.makedirs("maps/detailed", exist_ok=True)
        fn = f"maps/detailed/cluster_{cluster.id}_detail.html"
        m = folium.Map(location=cluster.center, zoom_start=14)
        color = self._color(cluster.id)
        
        # Office marker
        folium.Marker(self.office_location, popup="<b>Office</b>", 
                      icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        
        # Cluster center
        folium.Marker(cluster.center, popup=f"<b>Cluster {cluster.id} Center</b>", 
                      icon=folium.Icon(color='black', icon='star', prefix='fa')).add_to(m)
        
        # Track unique pickup points to draw bus stop markers
        pickup_points_drawn = set()
        
        # Employees with pickup lines
        for employee in cluster.employees:
            if employee.excluded:
                folium.CircleMarker(
                    location=employee.get_location(), radius=4, color='gray',
                    fill=True, fillColor='lightgray', fillOpacity=0.5,
                    popup=f"<b>ID:</b> {employee.id}<br><b>Status:</b> Excluded<br><b>Reason:</b> {employee.exclusion_reason}"
                ).add_to(m)
            else:
                # Get pickup point
                target_location = employee.pickup_point if hasattr(employee, 'pickup_point') and employee.pickup_point else None
                
                if target_location:
                    walk_distance = employee.distance_to(target_location[0], target_location[1])
                    
                    # Draw walking line (dashed)
                    folium.PolyLine(
                        [employee.get_location(), target_location],
                        color=color, weight=1.5, opacity=0.6, dash_array='5, 5',
                        popup=f"Walk: {walk_distance:.0f}m"
                    ).add_to(m)
                    
                    # Walking distance label at midpoint
                    midpoint = [(employee.lat + target_location[0]) / 2, (employee.lon + target_location[1]) / 2]
                    folium.Marker(
                        location=midpoint,
                        icon=folium.DivIcon(icon_size=(80, 20), icon_anchor=(40, 10), html=f'''
                            <div style="font-size: 10px; color: {color}; font-weight: bold; 
                                 background: rgba(255,255,255,0.8); padding: 1px 4px; border-radius: 3px;
                                 text-align: center;">{walk_distance:.0f}m</div>
                        ''')
                    ).add_to(m)
                    
                    # Draw bus stop marker (only once per unique location)
                    is_stop = hasattr(employee, 'pickup_type') and employee.pickup_type == 'stop'
                    stop_key = (round(target_location[0], 6), round(target_location[1], 6))
                    
                    if is_stop and stop_key not in pickup_points_drawn:
                        folium.Marker(
                            location=target_location,
                            icon=folium.DivIcon(
                                html='<div style="font-size: 18px; color: green; text-shadow: 1px 1px 2px white;"><i class="fa fa-bus"></i></div>',
                                icon_size=(20, 20), icon_anchor=(10, 10)
                            ),
                            popup="Pickup Stop"
                        ).add_to(m)
                        pickup_points_drawn.add(stop_key)
                
                # Employee marker
                folium.CircleMarker(
                    location=employee.get_location(), radius=5, color=color,
                    fill=True, fillColor=color, fillOpacity=0.7,
                    popup=f"<b>ID:</b> {employee.id}", weight=2
                ).add_to(m)
        
        # Route polyline
        if cluster.route and cluster.route.coordinates:
            folium.PolyLine(cluster.route.coordinates, color=color, weight=5, opacity=0.8,
                           popup=f"<b>Route</b><br>{cluster.route.distance_km:.1f} km<br>{cluster.route.duration_min:.0f} min").add_to(m)
        
        m.save(fn)
        return fn
    
    def create_zones_map(self, clusters: list[Cluster], zones=None, barrier_roads=None) -> str:
        fn = "maps/zones.html"
        all_emps = [e for c in clusters for e in c.employees]
        if not all_emps:
            return fn
        m = folium.Map(location=[sum(e.lat for e in all_emps)/len(all_emps), 
                                  sum(e.lon for e in all_emps)/len(all_emps)], zoom_start=12)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        
        if zones:
            for i, z in enumerate(zones):
                try:
                    if hasattr(z, 'exterior'):
                        folium.Polygon([[c[1], c[0]] for c in z.exterior.coords], color='#333', weight=2, fill=True, fill_opacity=0.1).add_to(m)
                except:
                    pass
        
        if barrier_roads:
            try:
                lines = barrier_roads.geoms if hasattr(barrier_roads, 'geoms') else [barrier_roads]
                for line in lines:
                    if hasattr(line, 'coords'):
                        folium.PolyLine([[c[1], c[0]] for c in line.coords], color='#dc2626', weight=4, opacity=0.8).add_to(m)
            except:
                pass
        
        for e in all_emps:
            folium.CircleMarker([e.lat, e.lon], radius=4, color=self._color(getattr(e, 'zone_id', 0)*10), fill=True).add_to(m)
        m.save(fn)
        return fn
    
    def create_all_maps(self, clusters: list[Cluster], zones=None, barrier_roads=None) -> list[str]:
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        all_emps = [e for c in clusters for e in c.employees]
        files = [self.create_employees_map(all_emps), self.create_clusters_map(clusters), self.create_routes_map(clusters)]
        if zones or barrier_roads:
            files.append(self.create_zones_map(clusters, zones, barrier_roads))
        for c in clusters:
            if c.route:  # Only create detailed maps for clusters with routes
                files.append(self.create_cluster_detail_map(c))
        return files


# =============================================================================
# Zone Service
# =============================================================================

class ZoneService:
    """Service for creating walkable zones based on road barriers."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.osm_file = getattr(config, 'OSM_FILE', 'data/istanbul-center.osm.pbf')
        self.barrier_types = getattr(config, 'BARRIER_ROAD_TYPES', 
                                     ['motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary'])
        self._osm = None
        self._barrier_roads = None
        self._zones = []
        self._stats = {}
    
    def _load_osm(self) -> None:
        if self._osm is None:
            self._osm = OSM(self.osm_file)
    
    def load_barrier_roads(self):
        self._load_osm()

        roads = self._osm.get_data_by_custom_criteria(
            custom_filter={"highway": self.barrier_types},
            filter_type="keep", keep_nodes=False, keep_ways=True, keep_relations=False
        )
        if roads is None or len(roads) == 0:

            return None
        self._barrier_roads = unary_union(roads.geometry)

        return self._barrier_roads
    
    def create_zones(self, employees: list[Employee]):
        if self._barrier_roads is None:
            self.load_barrier_roads()
        if self._barrier_roads is None:
            return []
        
        lats, lons = [e.lat for e in employees], [e.lon for e in employees]
        padding = 0.01
        bounds = box(min(lons)-padding, min(lats)-padding, max(lons)+padding, max(lats)+padding)
        clipped = self._barrier_roads.intersection(bounds)
        
        all_lines = unary_union([clipped, bounds.boundary]) if isinstance(clipped, (LineString, MultiLineString)) else bounds.boundary
        zones = [z for z in polygonize(all_lines) if z.area > 0.00001]
        self._zones = zones

        return zones
    
    def assign_employees_to_zones(self, employees: list[Employee]) -> dict:
        if not self._zones:
            self.create_zones(employees)
        
        assignments = {i: [] for i in range(len(self._zones))}
        for e in employees:
            pt = Point(e.lon, e.lat)
            assigned = False
            for i, z in enumerate(self._zones):
                if z.contains(pt):
                    e.zone_id = i
                    assignments[i].append(e)
                    assigned = True
                    break
            if not assigned:
                nearest = min(range(len(self._zones)), key=lambda i: self._zones[i].boundary.distance(pt))
                e.zone_id = nearest
                assignments[nearest].append(e)
        
        self._stats = {'total_zones': len(self._zones), 'empty_zones': sum(1 for v in assignments.values() if not v)}
        assignments = {k: v for k, v in assignments.items() if v}

        return assignments
    
    def get_zones(self):
        return self._zones
    
    def get_zone_stats(self):
        return self._stats
    
    def get_barrier_roads(self):
        return self._barrier_roads


# =============================================================================
# Service Planner (Main Orchestrator)
# =============================================================================

class ServicePlanner:
    """Main orchestrator for route optimization."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.employees: list[Employee] = []
        self.clusters: list[Cluster] = []
        self.vehicles: list[Vehicle] = []
        self.location_service = LocationService(config)
        self.clustering_service = ClusteringService(config)
        self.routing_service = RoutingService(config)
        self.visualization_service = VisualizationService(config)
        self.zone_service = ZoneService(config) if getattr(config, 'USE_ZONE_PARTITIONING', False) else None
        self.stats = {}
        self.zone_assignments = {}
        self.safe_stops = []
    
    @staticmethod
    def get_departure_time() -> datetime:
        t = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        return t + timedelta(days=1) if datetime.now().hour >= 8 else t
    
    def generate_employees(self, count: int | None = None, seed: int | None = None) -> list[Employee]:
        count = count or self.config.NUM_EMPLOYEES
        seed = seed if seed is not None else 42
        print(f"[1] Generating {count} employee locations...")
        self.employees = self.location_service.generate_employees(count, seed)
        print(f"    OK: {len(self.employees)} employees generated")
        return self.employees
    
    def create_zones(self) -> dict:
        if not self.zone_service:
            print("[2a] Zone partitioning (DISABLED)...")
            return {}
        print("[2a] Creating zones from road barriers...")
        self.zone_service.load_barrier_roads()
        self.zone_service.create_zones(self.employees)
        self.zone_assignments = self.zone_service.assign_employees_to_zones(self.employees)
        stats = self.zone_service.get_zone_stats()
        print(f"    OK: {stats['total_zones']} zones created, {len(self.zone_assignments)} non-empty")
        return self.zone_assignments
    
    def create_clusters(self, num_clusters: int | None = None) -> list[Cluster]:
        if self.zone_assignments:
            epc = getattr(self.config, 'EMPLOYEES_PER_CLUSTER', 20)
            print(f"[2b] Creating zone-aware clusters (~{epc} employees each)...")
            self.clusters = self.clustering_service.cluster_by_zones(self.zone_assignments, epc, 42)
        else:
            num_clusters = num_clusters or self.config.NUM_CLUSTERS
            print(f"[2b] Creating {num_clusters} clusters...")
            self.clusters = self.clustering_service.cluster_employees(self.employees, num_clusters, 42)
        print(f"    OK: {len(self.clusters)} clusters created")
        
        print("[2c] Snapping cluster centers to roads...")
        snapped = self.clustering_service.snap_centers_to_roads(self.clusters)
        print(f"    OK: {snapped}/{len(self.clusters)} snapped")
        
        cap = getattr(self.config, 'VEHICLE_CAPACITY', 50)
        print(f"[2d] Enforcing capacity (max {cap})...")
        valid, violations = self.clustering_service.validate_capacity(self.clusters, cap)
        if not valid:
            print(f"    {len(violations)} over capacity, splitting...")
            self.clusters = self.clustering_service.enforce_capacity_constraints(self.clusters, cap)
        print(f"    OK: {len(self.clusters)} clusters")
        return self.clusters
    
    def generate_stops(self) -> dict:
        print("[4] Finding farthest employees from office...")
        office_lat, office_lon = self.config.OFFICE_LOCATION
        count = 0
        for c in self.clusters:
            active = c.get_active_employees()
            if not active:
                continue
            farthest = max(active, key=lambda e: e.distance_to(office_lat, office_lon))
            c.set_stops([farthest.get_location(), c.center, self.config.OFFICE_LOCATION],
                       [0]*len(active) + [1, 2], [len(active), 0, 0])
            count += 1
        print(f"    OK: {count} routes created")
        return {'total_routes': count}
    
    def optimize_routes(self, use_stops: bool = True) -> list[Route]:
        min_emp = getattr(self.config, 'MIN_EMPLOYEES_FOR_SHUTTLE', 10)
        print(f"[5] Creating routes (min {min_emp} employees)...")
        routes, skipped = [], 0
        for c in self.clusters:
            if c.get_employee_count(False) < min_emp:
                skipped += 1
                continue
            route = self.routing_service.optimize_cluster_route(c, use_stops)
            if route:
                routes.append(route)
        
        for c in self.clusters:
            if c.route:
                c.route.match_employees_to_route(c.employees, self.safe_stops)
        
        print(f"    OK: {len(routes)} routes, {skipped} skipped")
        return routes
    
    def assign_vehicles(self) -> list[Vehicle]:
        cap = getattr(self.config, 'VEHICLE_CAPACITY', 50)
        vtype = getattr(self.config, 'VEHICLE_TYPE', 'Minibus')
        print(f"[7] Assigning vehicles (capacity: {cap})...")
        self.vehicles = []
        for i, c in enumerate(self.clusters):
            v = Vehicle(id=i+1, capacity=cap, vehicle_type=vtype)
            v.assign_cluster(c)
            v.set_departure_time(self.get_departure_time())
            c.assign_vehicle(v)
            self.vehicles.append(v)
        print(f"    OK: {len(self.vehicles)} vehicles")
        return self.vehicles
    
    def generate_maps(self) -> list[str]:
        print("[6] Generating maps...")
        zones = barrier_roads = None
        if self.zone_service:
            zones = self.zone_service.get_zones()
            barrier_roads = self.zone_service.get_barrier_roads()
        files = self.visualization_service.create_all_maps(self.clusters, zones, barrier_roads)
        print(f"    OK: {len(files)} maps created")
        return files
    
    def calculate_statistics(self) -> dict:
        total = len(self.employees)
        excluded = sum(1 for e in self.employees if e.excluded)
        dist = sum(c.route.distance_km for c in self.clusters if c.route)
        dur = sum(c.route.duration_min for c in self.clusters if c.route)
        self.stats = {
            'total_employees': total, 'active_employees': total-excluded,
            'excluded_employees': excluded, 'num_clusters': len(self.clusters),
            'num_vehicles': len(self.vehicles), 'total_distance_km': round(dist, 2),
            'total_duration_min': round(dur, 1)
        }
        return self.stats
    
    def print_summary(self) -> None:
        s = self.calculate_statistics()
        print("\n" + "="*50 + "\n                    SUMMARY\n" + "="*50)
        print(f"✓ Total Employees: {s['total_employees']}\n✓ Active: {s['active_employees']}\n✓ Excluded: {s['excluded_employees']}")
        print(f"✓ Clusters: {s['num_clusters']}\n✓ Vehicles: {s['num_vehicles']}")
        print(f"✓ Distance: {s['total_distance_km']} km\n✓ Duration: {s['total_duration_min']:.0f} min")
        print("="*50 + "\n")
    
    def run(self) -> None:
        print("\n" + "="*50 + "\n        SERVICE ROUTE OPTIMIZATION\n" + "="*50)
        print(f"   Config: {self.config.NUM_EMPLOYEES} employees, {self.config.NUM_CLUSTERS} clusters")
        print("="*50 + "\n")
        
        print("[0] Loading Safe Pickup Points...")
        self.safe_stops = self.location_service.get_transit_stops()
        print(f"    OK: {len(self.safe_stops)} stops loaded")
        
        self.generate_employees()
        self.create_zones()
        self.create_clusters()
        self.generate_stops()
        self.optimize_routes(use_stops=True)
        self.assign_vehicles()
        self.generate_maps()
        self.print_summary()
