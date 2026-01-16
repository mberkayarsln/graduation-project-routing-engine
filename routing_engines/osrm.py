"""OSRM Router - Open Source Routing Machine integration."""
import requests
from routing_engines.cache import APICache


class OSRMRouter:
    """Client for OSRM routing API."""
    
    def __init__(self, base_url="https://router.project-osrm.org", cache_enabled=True):
        self.base_url = base_url
        self.cache = APICache(cache_file='data/osrm_cache.json') if cache_enabled else None
    
    def get_route(self, points, profile='driving'):
        """
        Get optimal route between points.
        
        Args:
            points: List of (lat, lon) tuples
            profile: Routing profile ('driving', 'walking', 'cycling')
        
        Returns:
            Dict with 'coordinates', 'distance_km', 'duration_min'
        """
        if self.cache:
            cached_result = self.cache.get(points, departure_time=None)
            if cached_result is not None:
                return cached_result
        
        coords = ';'.join([f"{lon},{lat}" for lat, lon in points])
        url = f"{self.base_url}/route/v1/{profile}/{coords}"
        
        params = {
            'overview': 'full',
            'geometries': 'geojson'
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if 'routes' not in data or len(data['routes']) == 0:
                raise Exception("No route found")
            
            route_data = data['routes'][0]
            
            # Convert coordinates from [lon, lat] to [lat, lon]
            coordinates = [[coord[1], coord[0]] for coord in route_data['geometry']['coordinates']]
            
            distance_km = route_data['distance'] / 1000
            duration_min = route_data['duration'] / 60
            
            result = {
                'coordinates': coordinates,
                'distance_km': distance_km,
                'duration_min': duration_min
            }
            
            if self.cache:
                self.cache.set(points, departure_time=None, data=result)
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"OSRM API error: {e}")
            raise
        except KeyError as e:
            print(f"Unexpected OSRM response format: {e}")
            raise
            
    def get_distance_matrix(self, origins, destinations, profile='foot'):
        """
        Get distance matrix between origins and destinations.
        
        Args:
            origins: List of (lat, lon) tuples
            destinations: List of (lat, lon) tuples
            profile: Routing profile
        
        Returns:
            2D list of distances in meters
        """
        if self.cache:
            cached_result = self.cache.get_matrix(origins, destinations, profile)
            if cached_result is not None:
                return cached_result
        
        all_points = origins + destinations
        coords = ';'.join([f"{lon},{lat}" for lat, lon in all_points])
        
        url = f"{self.base_url}/table/v1/{profile}/{coords}"
        
        source_indices = ';'.join(map(str, range(len(origins))))
        dest_indices = ';'.join(map(str, range(len(origins), len(all_points))))
        
        params = {
            'sources': source_indices,
            'destinations': dest_indices,
            'annotations': 'distance'
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if 'code' in data and data['code'] != 'Ok':
                raise Exception(f"OSRM Error: {data.get('message', 'Unknown error')}")
            
            result = data['distances']
            
            if self.cache:
                self.cache.set_matrix(origins, destinations, profile, result)
                
            return result
            
        except Exception as e:
            print(f"OSRM Matrix API error: {e}")
            return None
    
    def snap_to_road(self, lat, lon, profile='driving'):
        """
        Snap a coordinate to the nearest point on the road network.
        
        Args:
            lat: Latitude
            lon: Longitude
            profile: Routing profile ('driving', 'walking', 'cycling')
        
        Returns:
            Dict with 'lat', 'lon', 'distance' (meters to snapped point), 'name' (road name)
            or None if snapping failed
        """
        url = f"{self.base_url}/nearest/v1/{profile}/{lon},{lat}"
        
        params = {
            'number': 1  # Return only the nearest point
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 'Ok' or not data.get('waypoints'):
                return None
            
            waypoint = data['waypoints'][0]
            snapped_lon, snapped_lat = waypoint['location']
            
            return {
                'lat': snapped_lat,
                'lon': snapped_lon,
                'distance': waypoint.get('distance', 0),
                'name': waypoint.get('name', '')
            }
            
        except requests.exceptions.RequestException as e:
            print(f"OSRM Nearest API error: {e}")
            return None
    
    def snap_points_to_road(self, points, profile='driving'):
        """
        Snap multiple coordinates to the nearest roads.
        
        Args:
            points: List of (lat, lon) tuples
            profile: Routing profile
        
        Returns:
            List of (lat, lon) tuples snapped to roads
        """
        snapped = []
        for lat, lon in points:
            result = self.snap_to_road(lat, lon, profile)
            if result:
                snapped.append((result['lat'], result['lon']))
            else:
                # Fallback to original if snapping fails
                snapped.append((lat, lon))
        return snapped
