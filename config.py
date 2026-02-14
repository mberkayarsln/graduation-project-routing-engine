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
    # Optimization Mode
    # =========================================================================
    # "balanced" (default), "budget" (fewer vehicles), "employee" (more vehicles)
    OPTIMIZATION_MODE: str = os.getenv("OPTIMIZATION_MODE", "balanced")
    
    # Mode presets override the parameters below when applied.
    # budget   → larger clusters, longer walks, fewer vehicles
    # employee → smaller clusters, shorter walks, more vehicles
    # balanced → default values below
    OPTIMIZATION_PRESETS: dict = {
        "budget": {
            "EMPLOYEES_PER_CLUSTER": 25,
            "VEHICLE_CAPACITY": 25,
            "MAX_WALK_DISTANCE": 1500,     # meters
            "MIN_EMPLOYEES_FOR_SHUTTLE": 5,
        },
        "balanced": {
            "EMPLOYEES_PER_CLUSTER": 17,
            "VEHICLE_CAPACITY": 17,
            "MAX_WALK_DISTANCE": 1000,
            "MIN_EMPLOYEES_FOR_SHUTTLE": 1,
        },
        "employee": {
            "EMPLOYEES_PER_CLUSTER": 10,
            "VEHICLE_CAPACITY": 10,
            "MAX_WALK_DISTANCE": 500,
            "MIN_EMPLOYEES_FOR_SHUTTLE": 1,
        },
    }
    
    # =========================================================================
    # Office Location
    # =========================================================================
    OFFICE_LOCATION: tuple[float, float] = (40.837384, 29.412109)
    
    # =========================================================================
    # Employee Generation
    # =========================================================================
    NUM_EMPLOYEES: int = 500
    NUM_CLUSTERS: int = 20
    
    # =========================================================================
    # Cluster & Stop Settings
    # =========================================================================
    EMPLOYEES_PER_CLUSTER: int = 17  # Maximum employees per cluster
    MIN_EMPLOYEES_FOR_SHUTTLE: int = 1  # Minimum employees to get shuttle service
    
    # =========================================================================
    # Walking & Road Snapping
    # =========================================================================
    MAX_WALK_DISTANCE: int = 1000  # Maximum walking distance in meters
    ROUTE_STOP_BUFFER_METERS: int = 15  # Max distance from route to consider a stop for assignment
    BUS_STOP_DISCOVERY_BUFFER_METERS: int = 30  # Max distance to discover/show stops along route
    FILTER_STOPS_BY_ROUTE_SIDE: bool = True  # Only show stops on the same side as route direction
    
    @classmethod
    def apply_optimization_mode(cls, mode: str | None = None) -> None:
        """Apply an optimization mode preset, overriding relevant parameters."""
        mode = (mode or cls.OPTIMIZATION_MODE).lower()
        preset = cls.OPTIMIZATION_PRESETS.get(mode)
        if not preset:
            return
        cls.OPTIMIZATION_MODE = mode
        for key, value in preset.items():
            setattr(cls, key, value)
    
    # =========================================================================
    # Zone Partitioning
    # =========================================================================
    USE_ZONE_PARTITIONING: bool = True
    OSM_FILE: str = "data/istanbul-anatolian.osm.pbf"
    BARRIER_ROAD_TYPES: list[str] = [
        "motorway", "motorway_link", "trunk", "trunk_link"
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
    
    # Load employees from database instead of generating new ones
    # Set to False to generate new random employees each run
    LOAD_EMPLOYEES_FROM_DB: bool = False
    
    # Clear all existing data before saving new data (for development/testing)
    TRUNCATE_DATABASE_ON_SAVE: bool = True
