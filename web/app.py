"""
Flask Web Application for Routing Engine Management.

Provides a REST API and web interface for managing:
- Employees
- Routes
- Clusters
- Vehicles
- Schedules
"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

load_dotenv()

from db.connection import Database
from db.repositories import (
    ZoneRepository, EmployeeRepository, ClusterRepository,
    RouteRepository, VehicleRepository
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize database and repositories
db = Database()
zone_repo = ZoneRepository(db)
employee_repo = EmployeeRepository(db)
cluster_repo = ClusterRepository(db)
route_repo = RouteRepository(db)
vehicle_repo = VehicleRepository(db)


# =============================================================================
# Web Pages
# =============================================================================

@app.route('/')
def dashboard():
    """Dashboard home page."""
    return render_template('dashboard.html')


@app.route('/employees')
def employees_page():
    """Employee management page."""
    return render_template('employees.html')


@app.route('/routes')
def routes_page():
    """Route management page."""
    return render_template('routes.html')


@app.route('/vehicles')
def vehicles_page():
    """Vehicle management page."""
    return render_template('vehicles.html')


@app.route('/routes/edit')
def routes_edit_page():
    """Route editing page with draggable waypoints."""
    return render_template('route_edit.html')


# =============================================================================
# REST API - Statistics
# =============================================================================

@app.route('/api/stats')
def api_stats():
    """Get dashboard statistics."""
    try:
        employees = employee_repo.find_all()
        clusters = cluster_repo.find_all()
        vehicles = vehicle_repo.find_all()
        zones = zone_repo.find_all()
        
        # Calculate route stats
        total_distance = 0
        total_duration = 0
        route_count = 0
        
        for cluster in clusters:
            route = route_repo.find_by_cluster(cluster.id)
            if route:
                total_distance += route.distance_km
                total_duration += route.duration_min
                route_count += 1
        
        excluded = sum(1 for e in employees if e.excluded)
        
        return jsonify({
            'total_employees': len(employees),
            'active_employees': len(employees) - excluded,
            'excluded_employees': excluded,
            'total_clusters': len(clusters),
            'total_routes': route_count,
            'total_vehicles': len(vehicles),
            'total_zones': len(zones),
            'total_distance_km': round(total_distance, 2),
            'total_duration_min': round(total_duration, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# REST API - Employees
# =============================================================================

@app.route('/api/employees')
def api_employees():
    """Get all employees."""
    try:
        employees = employee_repo.find_all()
        return jsonify([{
            'id': e.id,
            'name': e.name or f'Employee {e.id}',
            'lat': e.lat,
            'lon': e.lon,
            'zone_id': e.zone_id,
            'cluster_id': e.cluster_id,
            'excluded': e.excluded,
            'exclusion_reason': e.exclusion_reason,
            'pickup_type': e.pickup_type,
            'pickup_point': e.pickup_point
        } for e in employees])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/employees/<int:id>')
def api_employee(id):
    """Get single employee."""
    try:
        e = employee_repo.find_by_id(id)
        if not e:
            return jsonify({'error': 'Employee not found'}), 404
        return jsonify({
            'id': e.id,
            'name': e.name or f'Employee {e.id}',
            'lat': e.lat,
            'lon': e.lon,
            'zone_id': e.zone_id,
            'cluster_id': e.cluster_id,
            'excluded': e.excluded,
            'exclusion_reason': e.exclusion_reason,
            'pickup_type': e.pickup_type,
            'pickup_point': e.pickup_point
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/employees/<int:id>', methods=['PUT'])
def api_update_employee(id):
    """Update employee."""
    try:
        e = employee_repo.find_by_id(id)
        if not e:
            return jsonify({'error': 'Employee not found'}), 404
        
        data = request.json
        if 'excluded' in data:
            e.excluded = data['excluded']
        if 'exclusion_reason' in data:
            e.exclusion_reason = data['exclusion_reason']
        if 'pickup_type' in data:
            e.pickup_type = data['pickup_type']
        
        employee_repo.save(e)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# REST API - Clusters & Routes
# =============================================================================

@app.route('/api/clusters')
def api_clusters():
    """Get all clusters."""
    try:
        clusters = cluster_repo.find_all(include_employees=True)
        result = []
        for c in clusters:
            route = route_repo.find_by_cluster(c.id)
            result.append({
                'id': c.id,
                'center': c.center,
                'zone_id': c.zone_id,
                'employee_count': len(c.employees),
                'has_route': route is not None,
                'route_distance': route.distance_km if route else 0,
                'route_duration': route.duration_min if route else 0,
                'route_stops': route.stops if route else [],
                'route_coordinates': route.coordinates if route else []
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clusters/<int:id>')
def api_cluster(id):
    """Get single cluster with employees and route."""
    try:
        c = cluster_repo.find_by_id(id, include_employees=True)
        if not c:
            return jsonify({'error': 'Cluster not found'}), 404
        
        route = route_repo.find_by_cluster(id)
        
        return jsonify({
            'id': c.id,
            'center': c.center,
            'zone_id': c.zone_id,
            'employees': [{
                'id': e.id,
                'name': e.name or f'Employee {e.id}',
                'lat': e.lat,
                'lon': e.lon,
                'pickup_point': e.pickup_point
            } for e in c.employees],
            'route': {
                'distance_km': route.distance_km,
                'duration_min': route.duration_min,
                'stops': route.stops,
                'optimized': route.optimized
            } if route else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/routes')
def api_routes():
    """Get all routes with cluster info."""
    try:
        clusters = cluster_repo.find_all()
        routes = []
        for c in clusters:
            route = route_repo.find_by_cluster(c.id)
            if route:
                routes.append({
                    'cluster_id': c.id,
                    'center': c.center,
                    'distance_km': route.distance_km,
                    'duration_min': route.duration_min,
                    'stops': route.stops,
                    'coordinates': route.coordinates,
                    'stop_count': len(route.stops),
                    'optimized': route.optimized
                })
        return jsonify(routes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/routes/<int:cluster_id>', methods=['PUT'])
def api_update_route(cluster_id):
    """Update route stops for a cluster and reassign employee pickup points."""
    try:
        route = route_repo.find_by_cluster(cluster_id)
        if not route:
            return jsonify({'error': 'Route not found'}), 404
        
        data = request.json
        if 'stops' in data:
            route.stops = [tuple(s) for s in data['stops']]
        
        if 'coordinates' in data and data['coordinates']:
            route.coordinates = [list(c) for c in data['coordinates']]
        
        if 'distance_km' in data:
            route.distance_km = data['distance_km']
        
        if 'duration_min' in data:
            route.duration_min = data['duration_min']
        
        # Mark as modified (not optimized)
        route.optimized = False
            
        # Get cluster with employees
        cluster = cluster_repo.find_by_id(cluster_id, include_employees=True)
        vehicle_id = None
        
        # Reassign employees to nearest stops on the modified route
        matched_count = 0
        if cluster and cluster.employees and route.coordinates:
            # Load transit stops (bus stops) for proper matching
            from utils import DataGenerator
            data_gen = DataGenerator()
            safe_stops = data_gen.get_transit_stops()
            
            matched_count = route.match_employees_to_route(cluster.employees, safe_stops)
            
            # Update employee pickup points in database
            if matched_count > 0:
                for emp in cluster.employees:
                    if emp.pickup_point:
                        employee_repo.update_pickup_point(emp.id, emp.pickup_point)
        
        route_repo.save(route, cluster_id, vehicle_id)
            
        return jsonify({
            'success': True, 
            'employees_reassigned': matched_count
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# REST API - Vehicles
# =============================================================================

@app.route('/api/vehicles')
def api_vehicles():
    """Get all vehicles."""
    try:
        vehicles = vehicle_repo.find_all()
        return jsonify([{
            'id': v.id,
            'capacity': v.capacity,
            'vehicle_type': v.vehicle_type,
            'driver_name': v.driver_name
        } for v in vehicles])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/vehicles/<int:id>', methods=['PUT'])
def api_update_vehicle(id):
    """Update vehicle."""
    try:
        v = vehicle_repo.find_by_id(id)
        if not v:
            return jsonify({'error': 'Vehicle not found'}), 404
        
        data = request.json
        if 'driver_name' in data:
            v.driver_name = data['driver_name']
        if 'capacity' in data:
            v.capacity = data['capacity']
        
        vehicle_repo.save(v)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Run Server
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  Routing Engine Management Dashboard")
    print("="*50)
    print("  Open: http://localhost:5000")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
