"""
Configuration settings for the Service Route Optimization system.

This module centralizes all configuration parameters for employee generation,
clustering, routing, and visualization.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration for the route optimization system."""
    
    # =========================================================================
    # Office Location
    # =========================================================================
    OFFICE_LOCATION: tuple[float, float] = (41.1097, 29.0204)
    
    # =========================================================================
    # Employee Generation
    # =========================================================================
    NUM_EMPLOYEES: int = 300
    NUM_CLUSTERS: int = 20
    
    # =========================================================================
    # Cluster & Stop Settings
    # =========================================================================
    EMPLOYEES_PER_CLUSTER: int = 17  # Maximum employees per cluster
    EMPLOYEES_PER_STOP: int = 2
    MIN_STOPS_PER_CLUSTER: int = 1
    MAX_STOPS_PER_CLUSTER: int = 15
    MIN_EMPLOYEES_FOR_SHUTTLE: int = 10  # Minimum employees to get shuttle service
    
    # =========================================================================
    # Walking & Road Snapping
    # =========================================================================
    MAX_WALK_DISTANCE: int = 500  # Maximum walking distance in meters
    SNAP_STOPS_TO_ROADS: bool = True
    ROAD_SNAP_MAX_DISTANCE: int = 500  # Maximum snap distance in meters
    
    # =========================================================================
    # Zone Partitioning
    # =========================================================================
    USE_ZONE_PARTITIONING: bool = True
    OSM_FILE: str = "data/istanbul-center.osm.pbf"
    BARRIER_ROAD_TYPES: list[str] = [
        "motorway", "motorway_link", "trunk", "trunk_link", "primary"
    ]
    
    # =========================================================================
    # OSRM Routing
    # =========================================================================
    OSRM_URL: str = "http://localhost:5001"
    
    # =========================================================================
    # Vehicle Settings
    # =========================================================================
    VEHICLE_CAPACITY: int = 17  # Maximum passengers per vehicle
    VEHICLE_TYPE: str = "Minibus"
    
    # =========================================================================
    # Output Paths
    # =========================================================================
    OUTPUT_DIR: str = "maps"
    MAP_EMPLOYEES: str = f"{OUTPUT_DIR}/employees.html"
    MAP_CLUSTERS: str = f"{OUTPUT_DIR}/clusters.html"
    MAP_ROUTES: str = f"{OUTPUT_DIR}/optimized_routes.html"
    MAP_CLUSTER_DETAIL: str = f"{OUTPUT_DIR}/cluster_0_detail.html"
    
    # =========================================================================
    # Database Settings
    # =========================================================================
    DATABASE_HOST: str = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT: int = int(os.getenv("DATABASE_PORT", "5432"))
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "berkay")
    DATABASE_USER: str = os.getenv("DATABASE_USER", "berkay")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD", "")
    
    # Enable database persistence (set to False to run without database)
    USE_DATABASE: bool = os.getenv("USE_DATABASE", "true").lower() == "true"
    
    # Clear all existing data before saving new data (for development/testing)
    TRUNCATE_DATABASE_ON_SAVE: bool = True

