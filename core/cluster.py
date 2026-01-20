"""Cluster model - represents a group of employees assigned to a single route."""


class Cluster:
    """A cluster of employees that share a common pickup route."""
    
    def __init__(self, id, center):
        self.id = id
        self.center = center
        self.employees = []
        self.route = None
        self.vehicle = None
        self.stops = []
        self.stop_assignments = {}
        self.stop_loads = []
    
    def add_employee(self, employee):
        """Add an employee to this cluster."""
        self.employees.append(employee)
        employee.cluster_id = self.id
    
    
    def filter_by_distance(self, max_distance):
        """Exclude employees who are too far from the cluster center."""
        excluded_count = 0
        center_lat, center_lon = self.center
        
        for employee in self.employees:
            distance = employee.distance_to(center_lat, center_lon)
            if distance > max_distance:
                employee.exclude(f"Too far from center ({distance:.0f}m)")
                excluded_count += 1
        
        return excluded_count
    
    def get_active_employees(self):
        """Return list of non-excluded employees."""
        return [emp for emp in self.employees if not emp.excluded]
    
    def get_employee_count(self, include_excluded=False):
        """Return count of employees in this cluster."""
        if include_excluded:
            return len(self.employees)
        return len(self.get_active_employees())
    
    def get_employee_locations(self, include_excluded=False):
        """Return list of (lat, lon) tuples for employees."""
        employees = self.employees if include_excluded else self.get_active_employees()
        return [emp.get_location() for emp in employees]
    
    def assign_route(self, route):
        """Assign a route to this cluster."""
        self.route = route
        route.cluster = self
    
    def assign_vehicle(self, vehicle):
        """Assign a vehicle to this cluster."""
        self.vehicle = vehicle
        vehicle.cluster = self
    
    def set_stops(self, stops, assignments, stop_loads):
        """Set the stops for this cluster with employee assignments."""
        self.stops = stops
        self.stop_loads = stop_loads
        
        self.stop_assignments = {}
        active_employees = self.get_active_employees()
        
        for i, employee in enumerate(active_employees):
            if i < len(assignments):
                self.stop_assignments[employee.id] = assignments[i]
    
    def get_employee_stop(self, employee):
        """Get the stop assignment for an employee."""
        if employee.id in self.stop_assignments:
            stop_index = self.stop_assignments[employee.id]
            if stop_index < len(self.stops):
                return stop_index, self.stops[stop_index]
        return None, None
    
    def has_stops(self):
        """Check if this cluster has defined stops."""
        return len(self.stops) > 0
    
    def get_stats(self):
        """Return statistics about this cluster."""
        active = self.get_employee_count(include_excluded=False)
        total = self.get_employee_count(include_excluded=True)
        excluded = total - active
        
        stats = {
            'id': self.id,
            'center': self.center,
            'total_employees': total,
            'active_employees': active,
            'excluded_employees': excluded,
            'has_route': self.route is not None,
            'has_vehicle': self.vehicle is not None,
            'has_stops': self.has_stops(),
            'n_stops': len(self.stops)
        }
        
        if self.has_stops():
            stats['stop_loads'] = self.stop_loads
            stats['avg_load_per_stop'] = sum(self.stop_loads) / len(self.stop_loads) if self.stop_loads else 0
        
        if self.route:
            stats['route_distance_km'] = self.route.distance_km
            stats['route_duration_min'] = self.route.duration_min
        
        return stats
    
    def __repr__(self):
        return f"Cluster(id={self.id}, employees={len(self.employees)})"
    
    def __str__(self):
        active = self.get_employee_count(include_excluded=False)
        total = self.get_employee_count(include_excluded=True)
        return f"Cluster {self.id}: {active}/{total} employees"
