"""Zone Service - partitions urban area into walkable zones based on road barriers."""
from shapely.geometry import Point, box, MultiLineString, LineString
from shapely.ops import unary_union, polygonize
from pyrosm import OSM


class ZoneService:
    """Service for creating and managing walkable zones bounded by main roads."""
    
    def __init__(self, config):
        self.config = config
        self.osm_file = getattr(config, 'OSM_FILE', 'data/istanbul-center.osm.pbf')
        self.barrier_road_types = getattr(
            config, 
            'BARRIER_ROAD_TYPES', 
            ['motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary']
        )
        self._osm = None
        self._barrier_roads = None
        self._zones = []
        self._zone_stats = {}
    
    def _load_osm(self):
        """Load OSM data if not already loaded."""
        if self._osm is None:
            self._osm = OSM(self.osm_file)
    
    def load_barrier_roads(self):
        """
        Extract main roads from OSM that act as pedestrian barriers.
        
        Returns:
            MultiLineString geometry of all barrier roads
        """
        self._load_osm()
        
        print(f"   Loading barrier roads: {self.barrier_road_types}")
        
        roads = self._osm.get_data_by_custom_criteria(
            custom_filter={"highway": self.barrier_road_types},
            filter_type="keep",
            keep_nodes=False,
            keep_ways=True,
            keep_relations=False
        )
        
        if roads is None or len(roads) == 0:
            print("   WARNING: No barrier roads found!")
            return None
        
        # Combine all road geometries
        self._barrier_roads = unary_union(roads.geometry)
        
        print(f"   OK: Loaded {len(roads)} barrier road segments")
        
        return self._barrier_roads
    
    def create_zones(self, employees):
        """
        Partition the area into zones using barrier roads.
        
        Args:
            employees: List of Employee objects to determine bounds
            
        Returns:
            List of zone polygons
        """
        if self._barrier_roads is None:
            self.load_barrier_roads()
        
        if self._barrier_roads is None:
            print("   WARNING: Cannot create zones without barrier roads")
            return []
        
        # Calculate bounds from employee locations with padding
        lats = [e.lat for e in employees]
        lons = [e.lon for e in employees]
        padding = 0.01  # ~1km padding
        
        min_lon, max_lon = min(lons) - padding, max(lons) + padding
        min_lat, max_lat = min(lats) - padding, max(lats) + padding
        
        # Create bounding box
        bounds = box(min_lon, min_lat, max_lon, max_lat)
        
        # Clip barrier roads to bounding box
        clipped_barriers = self._barrier_roads.intersection(bounds)
        
        # Combine barriers with bounding box boundary for polygonization
        if isinstance(clipped_barriers, (LineString, MultiLineString)):
            all_lines = unary_union([clipped_barriers, bounds.boundary])
        else:
            all_lines = bounds.boundary
        
        # Polygonize to create zones
        zones = list(polygonize(all_lines))
        
        # Filter out zones outside the main area (very small slivers)
        min_zone_area = 0.00001  # Filter tiny zones
        zones = [z for z in zones if z.area > min_zone_area]
        
        self._zones = zones
        print(f"   OK: Created {len(zones)} zones from barrier roads")
        
        return zones
    
    def assign_employees_to_zones(self, employees):
        """
        Assign each employee to a zone.
        
        Args:
            employees: List of Employee objects
            
        Returns:
            Dict mapping zone_id -> list of employees
        """
        if not self._zones:
            print("   WARNING: No zones available, creating zones first")
            self.create_zones(employees)
        
        zone_assignments = {i: [] for i in range(len(self._zones))}
        unassigned = []
        
        for employee in employees:
            point = Point(employee.lon, employee.lat)
            assigned = False
            
            for zone_id, zone_polygon in enumerate(self._zones):
                if zone_polygon.contains(point):
                    employee.zone_id = zone_id
                    zone_assignments[zone_id].append(employee)
                    assigned = True
                    break
            
            if not assigned:
                # Find nearest zone for employees outside all polygons
                min_dist = float('inf')
                nearest_zone_id = 0
                
                for zone_id, zone_polygon in enumerate(self._zones):
                    dist = zone_polygon.boundary.distance(point)
                    if dist < min_dist:
                        min_dist = dist
                        nearest_zone_id = zone_id
                
                employee.zone_id = nearest_zone_id
                zone_assignments[nearest_zone_id].append(employee)
                unassigned.append(employee.id)
        
        if unassigned:
            print(f"   WARNING: {len(unassigned)} employees assigned to nearest zone")
        
        # Calculate zone statistics
        self._zone_stats = {
            'total_zones': len(self._zones),
            'employees_per_zone': {
                zone_id: len(emps) for zone_id, emps in zone_assignments.items()
            },
            'empty_zones': sum(1 for emps in zone_assignments.values() if len(emps) == 0),
            'unassigned_count': len(unassigned)
        }
        
        # Filter out empty zones from assignments
        zone_assignments = {
            zone_id: emps for zone_id, emps in zone_assignments.items() 
            if len(emps) > 0
        }
        
        print(f"   OK: Assigned employees to {len(zone_assignments)} zones")
        
        return zone_assignments
    
    def get_zones(self):
        """Return the zone polygons."""
        return self._zones
    
    def get_zone_stats(self):
        """Return zone statistics."""
        return self._zone_stats
    
    def get_barrier_roads(self):
        """Return the barrier road geometry."""
        return self._barrier_roads
