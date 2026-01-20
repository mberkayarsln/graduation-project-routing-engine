"""Routing Service - handles route optimization for clusters using OSRM."""
from routing_engines.osrm import OSRMRouter
from core.route import Route


class RoutingService:
    """Service for optimizing vehicle routes using OSRM."""
    
    def __init__(self, config):
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.osrm_router = OSRMRouter()
    
    def optimize_cluster_route(self, cluster, use_stops=True):
        """
        Optimize route for a single cluster using OSRM.
        
        Args:
            cluster: Cluster object to route
            use_stops: Whether to use predetermined stops
        
        Returns:
            Route object or None if no route possible
        """
        if use_stops and cluster.has_stops():
            route_stops = cluster.stops
            print(f"   Using {len(route_stops)} predetermined stops for cluster {cluster.id}")
        else:
            route_stops = cluster.get_employee_locations(include_excluded=False)
            print(f"   Using {len(route_stops)} employee locations for cluster {cluster.id}")
        
        if len(route_stops) == 0:
            return None
        
        route = Route(cluster=cluster)
        route.set_stops(route_stops)
        
        try:
            osrm_data = self.osrm_router.get_route(route_stops)
            route.coordinates = osrm_data['coordinates']
            route.distance_km = osrm_data['distance_km']
            route.duration_min = osrm_data['duration_min']
            print(f"   OK: OSRM route: {route.distance_km:.1f}km, {route.duration_min:.1f}min")
        except Exception as e:
            print(f"   ERROR: OSRM failed: {e}")
            route.calculate_stats_from_stops()
        
        cluster.assign_route(route)
        
        return route
