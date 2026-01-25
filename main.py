"""Service Route Optimization - Main Entry Point"""
from config import Config
from services import ServicePlanner


if __name__ == "__main__":
    planner = ServicePlanner(Config)
    planner.run()
