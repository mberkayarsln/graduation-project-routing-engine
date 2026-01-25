"""
Utility functions and classes for the route optimization system.

Contains: haversine, DataGenerator, KMeansClusterer
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from shapely.geometry import Point
from pyrosm import OSM
from sklearn.cluster import KMeans


# =============================================================================
# Geo Utilities
# =============================================================================

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# =============================================================================
# Data Generator
# =============================================================================

class DataGenerator:
    """Generates employee locations within urban residential areas."""
    
    def __init__(self, osm_file: str = "data/istanbul-center.osm.pbf") -> None:
        self.osm_file = osm_file
        self._osm: OSM | None = None
        self._urban_area = None
        self._bounds: tuple | None = None
    
    def _load_osm_data(self) -> None:
        if self._osm is None:
            self._osm = OSM(self.osm_file)
            landuse = self._osm.get_data_by_custom_criteria(
                custom_filter={"landuse": ["residential"]},
                filter_type="keep", keep_nodes=False, keep_ways=True, keep_relations=True
            )
            self._urban_area = landuse.unary_union
            self._bounds = landuse.total_bounds
            
    def get_transit_stops(self) -> list[tuple[float, float]]:
        self._load_osm_data()
        stops = self._osm.get_data_by_custom_criteria(
            custom_filter={
                "highway": ["bus_stop"], "railway": ["subway_entrance", "tram_stop"],
                "public_transport": ["platform", "stop_position"], "amenity": ["bus_station"]
            },
            filter_type="keep", keep_nodes=True, keep_ways=False, keep_relations=False
        )
        if stops is None or len(stops) == 0:
            return []
        return [(row.geometry.y, row.geometry.x) for _, row in stops.iterrows() 
                if hasattr(row.geometry, 'y')]
    
    def generate(self, n: int = 100, seed: int = 42) -> pd.DataFrame:
        self._load_osm_data()
        rng = np.random.default_rng(seed)
        points = []
        attempts = 0
        while len(points) < n and attempts < n * 30:
            lon = rng.uniform(self._bounds[0], self._bounds[2])
            lat = rng.uniform(self._bounds[1], self._bounds[3])
            if self._urban_area.contains(Point(lon, lat)):
                points.append((lat, lon))
            attempts += 1
        return pd.DataFrame({
            "id": np.arange(1, len(points) + 1),
            "lat": [p[0] for p in points], "lon": [p[1] for p in points]
        })


# =============================================================================
# KMeans Clusterer
# =============================================================================

class KMeansClusterer:
    """KMeans clustering wrapper."""
    
    def __init__(self, n_clusters: int = 5, random_state: int | None = 42, n_init: int = 10) -> None:
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.n_init = n_init
        self.model: KMeans | None = None
        self.cluster_centers_: np.ndarray | None = None
        self.labels_: np.ndarray | None = None
        self.inertia_: float | None = None
    
    def fit(self, coordinates: np.ndarray) -> KMeansClusterer:
        self.model = KMeans(n_clusters=self.n_clusters, random_state=self.random_state, n_init=self.n_init)
        self.labels_ = self.model.fit_predict(coordinates)
        self.cluster_centers_ = self.model.cluster_centers_
        self.inertia_ = self.model.inertia_
        return self
