"""
OSRM routing integration with caching.

Contains: APICache, OSRMRouter
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

import requests


# =============================================================================
# API Cache
# =============================================================================

class APICache:
    """File-based cache for API responses."""
    
    def __init__(self, cache_file: str = 'data/osrm_cache.json') -> None:
        self.cache_file = cache_file
        self.cache: dict = self._load_cache()
    
    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_cache(self) -> None:
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def _generate_key(self, points: list, departure_time: datetime | None) -> str:
        coords_str = '_'.join([f"{lat:.6f},{lon:.6f}" for lat, lon in points])
        time_str = departure_time.strftime('%Y-%m-%d-%H-%M') if departure_time else 'no-time'
        return hashlib.md5(f"{coords_str}_{time_str}".encode()).hexdigest()
    
    def get(self, points: list, departure_time: datetime | None) -> dict | None:
        key = self._generate_key(points, departure_time)
        return self.cache.get(key)
    
    def set(self, points: list, departure_time: datetime | None, data: dict) -> None:
        key = self._generate_key(points, departure_time)
        self.cache[key] = data.copy()
        self._save_cache()

    def _generate_matrix_key(self, origins: list, destinations: list, profile: str) -> str:
        o_str = '_'.join([f"{lat:.6f},{lon:.6f}" for lat, lon in origins])
        d_str = '_'.join([f"{lat:.6f},{lon:.6f}" for lat, lon in destinations])
        return hashlib.md5(f"matrix_{profile}_{o_str}_{d_str}".encode()).hexdigest()

    def get_matrix(self, origins: list, destinations: list, profile: str) -> list | None:
        return self.cache.get(self._generate_matrix_key(origins, destinations, profile))

    def set_matrix(self, origins: list, destinations: list, profile: str, data: list) -> None:
        self.cache[self._generate_matrix_key(origins, destinations, profile)] = data
        self._save_cache()


# =============================================================================
# OSRM Router
# =============================================================================

class OSRMRouter:
    """Client for OSRM routing API."""
    
    def __init__(self, base_url: str = "http://localhost:5001", cache_enabled: bool = True) -> None:
        self.base_url = base_url
        self.cache = APICache(cache_file='data/osrm_cache.json') if cache_enabled else None
    
    def get_route(self, points: list[tuple[float, float]], profile: str = 'driving') -> dict:
        if self.cache:
            cached = self.cache.get(points, departure_time=None)
            if cached:
                return cached
        
        coords = ';'.join([f"{lon},{lat}" for lat, lon in points])
        url = f"{self.base_url}/route/v1/{profile}/{coords}"
        
        try:
            resp = requests.get(url, params={'overview': 'full', 'geometries': 'geojson'}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if 'routes' not in data or not data['routes']:
                raise Exception("No route found")
            
            route = data['routes'][0]
            result = {
                'coordinates': [[c[1], c[0]] for c in route['geometry']['coordinates']],
                'distance_km': route['distance'] / 1000,
                'duration_min': route['duration'] / 60
            }
            
            if self.cache:
                self.cache.set(points, departure_time=None, data=result)
            return result
        except requests.exceptions.RequestException as e:
            print(f"OSRM API error: {e}")
            raise
            
    def get_distance_matrix(self, origins: list, destinations: list, profile: str = 'foot') -> list | None:
        if self.cache:
            cached = self.cache.get_matrix(origins, destinations, profile)
            if cached:
                return cached
        
        all_points = origins + destinations
        coords = ';'.join([f"{lon},{lat}" for lat, lon in all_points])
        url = f"{self.base_url}/table/v1/{profile}/{coords}"
        
        params = {
            'sources': ';'.join(map(str, range(len(origins)))),
            'destinations': ';'.join(map(str, range(len(origins), len(all_points)))),
            'annotations': 'distance'
        }
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get('code') != 'Ok':
                raise Exception(f"OSRM Error: {data.get('message')}")
            
            result = data['distances']
            if self.cache:
                self.cache.set_matrix(origins, destinations, profile, result)
            return result
        except Exception as e:
            print(f"OSRM Matrix API error: {e}")
            return None
    
    def snap_to_road(self, lat: float, lon: float, profile: str = 'driving') -> dict | None:
        try:
            resp = requests.get(
                f"{self.base_url}/nearest/v1/{profile}/{lon},{lat}",
                params={'number': 1}, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get('code') != 'Ok' or not data.get('waypoints'):
                return None
            
            wp = data['waypoints'][0]
            return {'lat': wp['location'][1], 'lon': wp['location'][0], 
                    'distance': wp.get('distance', 0), 'name': wp.get('name', '')}
        except:
            return None
