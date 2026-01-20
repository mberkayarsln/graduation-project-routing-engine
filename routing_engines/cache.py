"""API Cache - caches external API responses to reduce API calls."""
import json
import os
import hashlib
from datetime import datetime


class APICache:
    """File-based cache for API responses."""
    
    def __init__(self, cache_file='data/api_cache.json'):
        self.cache_file = cache_file
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Load cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: cache could not be loaded: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to file."""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def _generate_key(self, points, departure_time):
        """Generate a unique cache key from points and time."""
        coords_str = '_'.join([f"{lat:.6f},{lon:.6f}" for lat, lon in points])
        time_str = departure_time.strftime('%Y-%m-%d-%H-%M') if departure_time else 'no-time'
        key_str = f"{coords_str}_{time_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, points, departure_time):
        """Get cached result for given points and time."""
        key = self._generate_key(points, departure_time)
        
        if key in self.cache:
            cached_data = self.cache[key].copy()
            if 'departure_time' in cached_data and isinstance(cached_data['departure_time'], str):
                cached_data['departure_time'] = datetime.fromisoformat(cached_data['departure_time'])
            return cached_data
        
        return None
    
    def set(self, points, departure_time, data):
        """Cache result for given points and time."""
        key = self._generate_key(points, departure_time)
        
        cache_data = data.copy()
        if 'departure_time' in cache_data and isinstance(cache_data['departure_time'], datetime):
            cache_data['departure_time'] = cache_data['departure_time'].isoformat()
        
        self.cache[key] = cache_data
        self._save_cache()

    def _generate_matrix_key(self, origins, destinations, profile):
        """Generate cache key for distance matrix."""
        origins_str = '_'.join([f"{lat:.6f},{lon:.6f}" for lat, lon in origins])
        dests_str = '_'.join([f"{lat:.6f},{lon:.6f}" for lat, lon in destinations])
        key_str = f"matrix_{profile}_{origins_str}_{dests_str}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_matrix(self, origins, destinations, profile):
        """Get cached distance matrix."""
        key = self._generate_matrix_key(origins, destinations, profile)
        if key in self.cache:
            return self.cache[key]
        return None

    def set_matrix(self, origins, destinations, profile, data):
        """Cache distance matrix result."""
        key = self._generate_matrix_key(origins, destinations, profile)
        self.cache[key] = data
        self._save_cache()
