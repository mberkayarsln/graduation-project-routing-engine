"""Location Service - handles employee location generation and transit stops."""
from utils.data_generator import DataGenerator
from core.employee import Employee


class LocationService:
    """Service for generating and managing employee locations."""
    
    def __init__(self, config):
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.data_generator = DataGenerator()
    
    def generate_employees(self, count, seed=None):
        """
        Generate random employee locations.
        
        Args:
            count: Number of employees to generate
            seed: Random seed for reproducibility
        
        Returns:
            List of Employee objects
        """
        df = self.data_generator.generate(n=count, seed=seed)
        employees = []
        for _, row in df.iterrows():
            employee = Employee(
                id=int(row['id']),
                lat=row['lat'],
                lon=row['lon'],
                name=f"Employee {int(row['id'])}"
            )
            employees.append(employee)
        
        return employees
    
    def get_transit_stops(self):
        """Get list of transit stops from OSM data."""
        return self.data_generator.get_transit_stops()
