"""Service Planner - main orchestrator for route optimization."""
from services.location import LocationService
from services.clustering import ClusteringService
from services.routing import RoutingService
from services.visualization import VisualizationService
from services.zone_service import ZoneService
from core.vehicle import Vehicle
from datetime import datetime, timedelta


class ServicePlanner:
    """Main orchestrator that coordinates all services for route planning."""
    
    def __init__(self, config):
        self.config = config
        
        # Data containers
        self.employees = []
        self.clusters = []
        self.vehicles = []
        
        # Services
        self.location_service = LocationService(config)
        self.clustering_service = ClusteringService(config)
        self.routing_service = RoutingService(config)
        self.visualization_service = VisualizationService(config)
        self.zone_service = ZoneService(config) if getattr(config, 'USE_ZONE_PARTITIONING', False) else None
        
        # State
        self.stats = {}
        self.zone_assignments = {}
        self.safe_stops = []
    
    @staticmethod
    def get_departure_time():
        """Get next 8 AM departure time."""
        tomorrow_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        if datetime.now().hour >= 8:
            tomorrow_8am += timedelta(days=1)
        return tomorrow_8am
    
    def generate_employees(self, count=None, seed=None):
        """Generate employee locations."""
        count = count or self.config.NUM_EMPLOYEES
        seed = seed if seed is not None else 42
        
        print(f"[1] Generating {count} employee locations...")
        self.employees = self.location_service.generate_employees(count, seed)
        print(f"    OK: {len(self.employees)} employees generated")
        
        return self.employees
    
    def create_zones(self):
        """Create walkable zones based on road barriers."""
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
    
    def create_clusters(self, num_clusters=None):
        """Cluster employees into groups."""
        # Use zone-aware clustering if zones are available
        if self.zone_assignments:
            employees_per_cluster = getattr(self.config, 'EMPLOYEES_PER_CLUSTER', 20)
            print(f"[2b] Creating zone-aware clusters (~{employees_per_cluster} employees each)...")
            
            self.clusters = self.clustering_service.cluster_by_zones(
                self.zone_assignments,
                employees_per_cluster=employees_per_cluster,
                random_state=42
            )
            print(f"    OK: {len(self.clusters)} clusters created across {len(self.zone_assignments)} zones")
        else:
            # Fallback to traditional clustering
            num_clusters = num_clusters or self.config.NUM_CLUSTERS
            print(f"[2b] Creating {num_clusters} clusters...")
            
            self.clusters = self.clustering_service.cluster_employees(
                self.employees,
                num_clusters,
                random_state=42
            )
            print(f"    OK: {len(self.clusters)} clusters created")
        
        # Snap cluster centers to roads
        self.snap_cluster_centers()
        
        return self.clusters
    
    def snap_cluster_centers(self):
        """Snap cluster centers to the nearest roads."""
        print(f"[2c] Snapping cluster centers to roads...")
        snapped = self.clustering_service.snap_centers_to_roads(self.clusters)
        print(f"    OK: {snapped}/{len(self.clusters)} cluster centers snapped to roads")
    
    def filter_employees_by_distance(self):
        """Filter out employees too far from cluster centers."""
        max_distance = self.config.MAX_DISTANCE_FROM_CENTER
        
        if max_distance is None:
            print("[3] Filtering distant employees (DISABLED)...")
            return 0
            
        total_excluded = 0
        
        print(f"[3] Filtering distant employees (max: {max_distance/1000}km)...")
        for cluster in self.clusters:
            excluded = cluster.filter_by_distance(max_distance)
            total_excluded += excluded
        
        print(f"    OK: {total_excluded} employees excluded")
        
        return total_excluded
    
    def generate_stops(self):
        """Generate pickup stops for each cluster."""
        print(f"[4] Finding farthest employees from office in each cluster...")
        
        office_lat, office_lon = self.config.OFFICE_LOCATION
        total_routes = 0
        
        for cluster in self.clusters:
            active_employees = cluster.get_active_employees()
            
            if len(active_employees) == 0:
                continue
            
            # Find farthest employee from office
            max_distance = 0
            farthest_employee = None
            
            for employee in active_employees:
                distance = employee.distance_to(office_lat, office_lon)
                if distance > max_distance:
                    max_distance = distance
                    farthest_employee = employee
            
            if farthest_employee:
                cluster_center = cluster.center
                route_points = [
                    farthest_employee.get_location(),
                    cluster_center,
                    self.config.OFFICE_LOCATION
                ]
                
                cluster.set_stops(
                    stops=route_points,
                    assignments=[0] * len(active_employees) + [1, 2],
                    stop_loads=[len(active_employees), 0, 0]
                )
                
                total_routes += 1
                print(f"   Cluster {cluster.id}: Farthest employee {farthest_employee.id} "
                      f"at {max_distance/1000:.2f}km → cluster center → office")
        
        print(f"    OK: {total_routes} direct routes created")
        
        return {'total_routes': total_routes}
    
    def optimize_routes(self, use_stops=True):
        """Optimize routes for all clusters using OSRM."""
        mode = "stops" if use_stops else "employee locations"
        print(f"[5] Creating routes ({mode})...")
        
        routes = []
        
        for cluster in self.clusters:
            route = self.routing_service.optimize_cluster_route(
                cluster=cluster,
                use_stops=use_stops
            )
            if route:
                routes.append(route)
        
        # Match employees to routes
        for i, cluster in enumerate(self.clusters):
            if cluster.route:
                print(f"   Matching employees to route for cluster {cluster.id}...")
                matched = cluster.route.match_employees_to_route(cluster.employees, safe_stops=self.safe_stops)
                print(f"   Matched {matched} employees to route points")

            if cluster.route:
                active = cluster.get_employee_count(include_excluded=False)
                if use_stops and cluster.has_stops():
                    n_stops = len(cluster.stops)
                else:
                    n_stops = len(cluster.route.stops) - 1 if len(cluster.route.stops) > 0 else 0
                
                print(f"   Cluster {cluster.id}: {active} employees → {n_stops} stops")
        
        print(f"    OK: {len(routes)} routes created")
        
        return routes
    
    def assign_vehicles(self):
        """Assign vehicles to clusters."""
        print(f"Assigning vehicles...")
        
        self.vehicles = []
        for i, cluster in enumerate(self.clusters):
            vehicle = Vehicle(
                id=i + 1,
                capacity=50,
                vehicle_type="Minibus"
            )
            vehicle.assign_cluster(cluster)
            vehicle.set_departure_time(self.get_departure_time())
            cluster.assign_vehicle(vehicle)
            self.vehicles.append(vehicle)
        
        print(f"    OK: {len(self.vehicles)} vehicles assigned")
        
        return self.vehicles
    
    def generate_maps(self):
        """Generate HTML map visualizations."""
        print(f"[6] Generating maps...")
        
        # Get zone data if available
        zones = None
        barrier_roads = None
        if self.zone_service:
            zones = self.zone_service.get_zones()
            barrier_roads = self.zone_service.get_barrier_roads()
        
        files = self.visualization_service.create_all_maps(
            self.clusters, 
            zones=zones, 
            barrier_roads=barrier_roads
        )
        
        print(f"    OK: {files[0]} (employees)")
        print(f"    OK: {files[1]} (clusters)")
        print(f"    OK: {files[2]} (routes)")
        
        if zones:
            print(f"    OK: maps/zones.html (zone boundaries)")
        
        if len(files) > 3 + (1 if zones else 0):
            detail_count = len(files) - 3 - (1 if zones else 0)
            print(f"    OK: {detail_count} detailed cluster maps created")
        
        return files
    
    def calculate_statistics(self):
        """Calculate summary statistics."""
        total_employees = len(self.employees)
        excluded_employees = sum(1 for emp in self.employees if emp.excluded)
        active_employees = total_employees - excluded_employees
        
        total_distance = 0
        total_duration = 0
        
        for cluster in self.clusters:
            if cluster.route:
                total_distance += cluster.route.distance_km
                total_duration += cluster.route.duration_min
        
        self.stats = {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'excluded_employees': excluded_employees,
            'num_clusters': len(self.clusters),
            'num_vehicles': len(self.vehicles),
            'total_distance_km': round(total_distance, 2),
            'total_duration_min': round(total_duration, 1)
        }
        
        return self.stats
    
    def print_summary(self):
        """Print execution summary."""
        stats = self.calculate_statistics()
        
        print("\n" + "=" * 50)
        print("                    SUMMARY")
        print("=" * 50)
        print(f"✓ Total Employees: {stats['total_employees']}")
        print(f"✓ Active Employees: {stats['active_employees']}")
        print(f"✓ Excluded: {stats['excluded_employees']}")
        print(f"✓ Clusters: {stats['num_clusters']}")
        print(f"✓ Vehicles: {stats['num_vehicles']}")
        print(f"✓ Total Distance: {stats['total_distance_km']} km")
        print(f"✓ Total Duration: {stats['total_duration_min']:.0f} minutes")
        print("=" * 50 + "\n")
    
    def run(self):
        """Execute the full route optimization pipeline."""
        print("\n" + "=" * 50)
        print("        SERVICE ROUTE OPTIMIZATION")
        print("=" * 50)
        print(f"   Config: {self.config.NUM_EMPLOYEES} employees, {self.config.NUM_CLUSTERS} clusters")
        print("=" * 50 + "\n")
        
        print("[0] Loading Safe Pickup Points (Bus/Metro Stops)...")
        self.safe_stops = self.location_service.get_transit_stops()
        print(f"    OK: {len(self.safe_stops)} safe stops loaded from OSM")
        
        self.generate_employees()
        self.create_zones()
        self.create_clusters()
        self.filter_employees_by_distance()
        self.generate_stops()
        self.optimize_routes(use_stops=True)
        self.assign_vehicles()
        self.generate_maps()
        self.print_summary()
