"""Data Generator - generates synthetic employee locations from OSM data."""
import numpy as np
import pandas as pd
from shapely.geometry import Point
from pyrosm import OSM


class DataGenerator:
    """Generates employee locations within urban residential areas."""
    
    def __init__(self, osm_file="data/istanbul-center.osm.pbf"):
        self.osm_file = osm_file
        self._osm = None
        self._urban_area = None
        self._bounds = None
    
    def _load_osm_data(self):
        """Load and cache OSM data."""
        if self._osm is None:
            self._osm = OSM(self.osm_file)
            
            landuse = self._osm.get_data_by_custom_criteria(
                custom_filter={"landuse": ["residential"]},
                filter_type="keep",
                keep_nodes=False,
                keep_ways=True,
                keep_relations=True
            )
            
            self._urban_area = landuse.unary_union
            self._bounds = landuse.total_bounds
            
    def get_transit_stops(self):
        """Get bus and metro stops from OSM data."""
        self._load_osm_data()
        
        custom_filter = {
            "highway": ["bus_stop"],
            "railway": ["subway_entrance", "tram_stop"],
            "public_transport": ["platform", "stop_position"],
            "amenity": ["bus_station"]
        }
        
        stops = self._osm.get_data_by_custom_criteria(
            custom_filter=custom_filter,
            filter_type="keep",
            keep_nodes=True,
            keep_ways=False,
            keep_relations=False
        )
        
        if stops is None or len(stops) == 0:
            return []
            
        stops_list = []
        for _, row in stops.iterrows():
            if hasattr(row.geometry, 'y') and hasattr(row.geometry, 'x'):
                stops_list.append((row.geometry.y, row.geometry.x))
                
        return stops_list
    
    def generate(self, n=100, seed=42):
        """
        Generate n random employee locations within residential areas.
        
        Args:
            n: Number of employees to generate
            seed: Random seed for reproducibility
        
        Returns:
            DataFrame with id, lat, lon columns
        """
        self._load_osm_data()
        
        rng = np.random.default_rng(seed)
        points = []
        attempts = 0
        max_attempts = n * 30
        
        while len(points) < n and attempts < max_attempts:
            lon = rng.uniform(self._bounds[0], self._bounds[2])
            lat = rng.uniform(self._bounds[1], self._bounds[3])
            p = Point(lon, lat)
            
            if self._urban_area.contains(p):
                points.append((lat, lon))
            
            attempts += 1
        
        df = pd.DataFrame({
            "id": np.arange(1, len(points) + 1),
            "lat": [p[0] for p in points],
            "lon": [p[1] for p in points],
        })
        
        return df
