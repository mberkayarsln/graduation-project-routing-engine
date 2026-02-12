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

# Cache for transit stops to avoid reloading OSM data on every request
_transit_stops_cache: list[tuple[float, float]] | None = None


def _get_transit_stops_cached() -> list[tuple[float, float]]:
    global _transit_stops_cache
    if _transit_stops_cache is None:
        from utils import DataGenerator
        data_gen = DataGenerator()
        _transit_stops_cache = data_gen.get_transit_stops()
    return _transit_stops_cache


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


@app.route('/clusters')
def clusters_page():
    """Cluster management page."""
    return render_template('clusters.html')


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
        
        # Calculate route stats and track which clusters have routes
        total_distance = 0
        total_duration = 0
        route_count = 0
        clusters_with_routes = set()
        
        for cluster in clusters:
            route = route_repo.find_by_cluster(cluster.id)
            if route:
                total_distance += route.distance_km
                total_duration += route.duration_min
                route_count += 1
                clusters_with_routes.add(cluster.id)
        
        excluded = sum(1 for e in employees if e.excluded)
        # Unassigned = active employees whose cluster doesn't have a route
        unassigned = sum(1 for e in employees if not e.excluded and (e.cluster_id is None or e.cluster_id not in clusters_with_routes))
        
        return jsonify({
            'total_employees': len(employees),
            'active_employees': len(employees) - excluded,
            'excluded_employees': excluded,
            'unassigned_employees': unassigned,
            'total_clusters': len(clusters),
            'total_routes': route_count,
            'total_vehicles': len(vehicles),
            'total_zones': len(zones),
            'total_distance_km': round(total_distance, 2),
            'total_duration_min': round(total_duration, 1)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/optimization-mode', methods=['GET'])
def api_get_optimization_mode():
    """Get current optimization mode and available presets."""
    from config import Config
    return jsonify({
        'current_mode': getattr(Config, 'OPTIMIZATION_MODE', 'balanced'),
        'presets': Config.OPTIMIZATION_PRESETS
    })


@app.route('/api/generate-routes', methods=['POST'])
def api_generate_routes():
    """Trigger route generation. Accepts optional JSON body: { "mode": "budget"|"balanced"|"employee" }"""
    try:
        from config import Config
        from services import ServicePlanner
        
        # Read optimization mode from request
        mode = None
        if request.is_json and request.json:
            mode = request.json.get('mode')
        
        # Run route generation with selected mode
        planner = ServicePlanner(Config)
        planner.run(optimization_mode=mode)
        
        # Return updated stats
        employees = employee_repo.find_all()
        clusters = cluster_repo.find_all()
        vehicles = vehicle_repo.find_all()
        
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
            'success': True,
            'message': 'Routes generated successfully',
            'stats': {
                'total_employees': len(employees),
                'active_employees': len(employees) - excluded,
                'total_routes': route_count,
                'total_vehicles': len(vehicles),
                'total_distance_km': round(total_distance, 2),
                'total_duration_min': round(total_duration, 1)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# REST API - Employees
# =============================================================================

@app.route('/api/employees')
def api_employees():
    """Get all employees."""
    try:
        employees = employee_repo.find_all()
        clusters = cluster_repo.find_all()
        
        # Find which clusters have routes
        clusters_with_routes = set()
        for cluster in clusters:
            route = route_repo.find_by_cluster(cluster.id)
            if route:
                clusters_with_routes.add(cluster.id)
        
        return jsonify([{
            'id': e.id,
            'name': e.name or f'Employee {e.id}',
            'lat': e.lat,
            'lon': e.lon,
            'zone_id': e.zone_id,
            'cluster_id': e.cluster_id,
            'excluded': e.excluded,
            'exclusion_reason': e.exclusion_reason,
            'pickup_point': e.pickup_point,
            'has_route': e.cluster_id is not None and e.cluster_id in clusters_with_routes
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
        
        # Calculate walking distances using OSRM
        walking_distances = {}
        employees_with_pickup = [e for e in c.employees if e.pickup_point]
        
        if employees_with_pickup:
            try:
                from routing import OSRMRouter
                router = OSRMRouter()
                
                emp_locs = [(e.lat, e.lon) for e in employees_with_pickup]
                pickup_locs = [e.pickup_point for e in employees_with_pickup]
                
                # Get distance matrix from employees to their pickup points
                distances = router.get_distance_matrix(emp_locs, pickup_locs, profile='foot')
                
                if distances:
                    for i, emp in enumerate(employees_with_pickup):
                        # Distance from employee i to their own pickup point (diagonal)
                        if distances[i] and len(distances[i]) > i:
                            walking_distances[emp.id] = distances[i][i]
            except Exception as e:
                print(f"Error calculating walking distances: {e}")
        
        return jsonify({
            'id': c.id,
            'center': c.center,
            'zone_id': c.zone_id,
            'employees': [{
                'id': e.id,
                'name': e.name or f'Employee {e.id}',
                'lat': e.lat,
                'lon': e.lon,
                'pickup_point': e.pickup_point,
                'walking_distance': walking_distances.get(e.id)
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
        include_bus_stops = request.args.get('include_bus_stops', 'false').lower() == 'true'
        clusters = cluster_repo.find_all(include_employees=False)
        all_transit_stops = _get_transit_stops_cached() if include_bus_stops else []
        
        routes = []
        for c in clusters:
            route = route_repo.find_by_cluster(c.id)
            if route:
                # Find all bus stops along this route only if requested
                bus_stops = []
                if include_bus_stops:
                    from config import Config
                    discovery_buffer = getattr(Config, 'BUS_STOP_DISCOVERY_BUFFER_METERS', 150)
                    same_side = getattr(Config, 'FILTER_STOPS_BY_ROUTE_SIDE', True)
                    bus_stops = route.find_all_stops_along_route(all_transit_stops, buffer_meters=discovery_buffer, same_side_only=same_side)
                employee_count = employee_repo.count_by_cluster(c.id)
                
                routes.append({
                    'cluster_id': c.id,
                    'center': c.center,
                    'distance_km': route.distance_km,
                    'duration_min': route.duration_min,
                    'stops': route.stops,
                    'bus_stops': bus_stops,
                    'coordinates': route.coordinates,
                    'stop_count': len(route.stops),
                    'bus_stop_count': len(bus_stops),
                    'employee_count': employee_count,
                    'optimized': route.optimized
                })
        return jsonify(routes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/routes/<int:cluster_id>', methods=['GET'])
def api_get_route(cluster_id):
    """Get a single route with full details including bus stops."""
    try:
        cluster = cluster_repo.find_by_id(cluster_id, include_employees=False)
        if not cluster:
            return jsonify({'error': 'Cluster not found'}), 404
        
        route = route_repo.find_by_cluster(cluster_id)
        if not route:
            return jsonify({'error': 'Route not found'}), 404
        
        # Always include bus stops for detail view
        from config import Config
        all_transit_stops = _get_transit_stops_cached()
        discovery_buffer = getattr(Config, 'BUS_STOP_DISCOVERY_BUFFER_METERS', 150)
        same_side = getattr(Config, 'FILTER_STOPS_BY_ROUTE_SIDE', True)
        bus_stops = route.find_all_stops_along_route(all_transit_stops, buffer_meters=discovery_buffer, same_side_only=same_side)
        employee_count = employee_repo.count_by_cluster(cluster_id)
        
        return jsonify({
            'cluster_id': cluster.id,
            'center': cluster.center,
            'distance_km': route.distance_km,
            'duration_min': route.duration_min,
            'stops': route.stops,
            'bus_stops': bus_stops,
            'coordinates': route.coordinates,
            'stop_count': len(route.stops),
            'bus_stop_count': len(bus_stops),
            'employee_count': employee_count,
            'optimized': route.optimized
        })
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
        bus_stops = []
        if cluster and cluster.employees and route.coordinates:
            # Load transit stops (bus stops) for proper matching
            from utils import DataGenerator
            data_gen = DataGenerator()
            safe_stops = data_gen.get_transit_stops()
            from config import Config
            
            # Find all bus stops along the new route
            discovery_buffer = getattr(Config, 'BUS_STOP_DISCOVERY_BUFFER_METERS', 150)
            same_side = getattr(Config, 'FILTER_STOPS_BY_ROUTE_SIDE', True)
            bus_stops = route.find_all_stops_along_route(safe_stops, buffer_meters=discovery_buffer, same_side_only=same_side)
            
            stop_buffer = getattr(Config, 'ROUTE_STOP_BUFFER_METERS', 150)
            matched_count = route.match_employees_to_route(
                cluster.employees,
                safe_stops,
                buffer_meters=stop_buffer,
            )
            
            # Update employee pickup points in database
            if matched_count > 0:
                for emp in cluster.employees:
                    if emp.pickup_point:
                        employee_repo.update_pickup_point(emp.id, emp.pickup_point)
        
        route_repo.save(route, cluster_id, vehicle_id)
            
        return jsonify({
            'success': True, 
            'employees_reassigned': matched_count,
            'bus_stops': bus_stops,
            'bus_stop_count': len(bus_stops)
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
# REST API - Bus Stop Names
# =============================================================================

# Cache for transit stop names (separate from coordinates cache)
_transit_stop_names_cache: dict[tuple[float, float], str] | None = None

@app.route('/api/stops/names', methods=['POST'])
def api_stop_names():
    """Look up bus stop names by coordinates."""
    global _transit_stop_names_cache
    
    try:
        # Load transit stops with names (cached)
        if _transit_stop_names_cache is None:
            from utils import DataGenerator
            data_gen = DataGenerator()
            _transit_stop_names_cache = data_gen.get_transit_stops_with_names()
        
        data = request.json
        coordinates = data.get('coordinates', [])  # List of [lat, lon] pairs
        
        results = {}
        for coord in coordinates:
            lat, lon = coord[0], coord[1]
            # Find nearest stop within ~50m (0.0005 degrees)
            best_name = None
            best_dist = float('inf')
            for (stop_lat, stop_lon), name in _transit_stop_names_cache.items():
                dist = abs(stop_lat - lat) + abs(stop_lon - lon)
                if dist < 0.0005 and dist < best_dist:
                    best_dist = dist
                    best_name = name
            
            key = f"{lat:.5f},{lon:.5f}"
            results[key] = best_name or 'Bus Stop'
        
        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# REST API - Cost Report
# =============================================================================

@app.route('/cost-report')
def cost_report_page():
    """Cost report page for tender presentations."""
    return render_template('cost_report.html')


@app.route('/api/cost-report')
def api_cost_report():
    """Calculate comprehensive cost report including Turkish taxes."""
    try:
        from config import Config
        
        # Fetch real data from database
        employees = employee_repo.find_all()
        clusters = cluster_repo.find_all()
        vehicles = vehicle_repo.find_all()
        
        total_distance = 0.0
        total_duration = 0.0
        route_count = 0
        for cluster in clusters:
            route = route_repo.find_by_cluster(cluster.id)
            if route:
                total_distance += float(route.distance_km)
                total_duration += float(route.duration_min)
                route_count += 1
        
        active_employees = sum(1 for e in employees if not e.excluded)
        vehicle_count = len(vehicles) if vehicles else route_count
        
        # Override defaults with query parameters
        def qp(name, default):
            val = request.args.get(name)
            return float(val) if val is not None else default
        
        # === Cost Parameters (overridable) ===
        driver_gross_salary   = qp('driver_salary', 35000)       # ₺/month
        sgk_employer_rate     = qp('sgk_rate', 22.5) / 100       # 22.5%
        unemployment_rate     = qp('unemployment_rate', 2) / 100  # 2%
        vehicle_rent          = qp('vehicle_rent', 25000)         # ₺/month per vehicle
        fuel_price_per_liter  = qp('fuel_price', 43.5)            # ₺/liter
        fuel_consumption      = qp('fuel_consumption', 15)        # liters/100km
        maintenance_monthly   = qp('maintenance', 8000)           # ₺/month per vehicle
        mtv_monthly           = qp('mtv', 1500)                   # ₺/month per vehicle
        working_days          = qp('working_days', 22)            # days/month
        trips_per_day         = qp('trips_per_day', 2)            # round-trip (morning+evening)
        overhead_rate         = qp('overhead_rate', 5) / 100      # 5%
        profit_rate           = qp('profit_rate', 10) / 100       # 10%
        kdv_rate              = qp('kdv_rate', 20) / 100          # 20%
        stamp_tax_rate        = qp('stamp_tax_rate', 0.948) / 100 # 0.948%
        contract_months       = qp('contract_months', 12)         # months
        
        # === Calculations ===
        
        # 1. Driver costs (per vehicle, monthly)
        sgk_cost = driver_gross_salary * sgk_employer_rate
        unemployment_cost = driver_gross_salary * unemployment_rate
        driver_total_per_vehicle = driver_gross_salary + sgk_cost + unemployment_cost
        driver_total = driver_total_per_vehicle * vehicle_count
        
        # 2. Vehicle costs (monthly, all vehicles)
        vehicle_rent_total = vehicle_rent * vehicle_count
        maintenance_total = maintenance_monthly * vehicle_count
        mtv_total = mtv_monthly * vehicle_count
        vehicle_total = vehicle_rent_total + maintenance_total + mtv_total
        
        # 3. Fuel costs (monthly, all routes)
        daily_km = total_distance * trips_per_day
        monthly_km = daily_km * working_days
        fuel_liters_monthly = monthly_km * fuel_consumption / 100
        fuel_total = fuel_liters_monthly * fuel_price_per_liter
        
        # 4. Subtotal (before overhead/profit/taxes)
        subtotal = driver_total + vehicle_total + fuel_total
        
        # 5. Overhead
        overhead_total = subtotal * overhead_rate
        
        # 6. Net operational cost
        net_cost = subtotal + overhead_total
        
        # 7. Profit margin
        profit_total = net_cost * profit_rate
        
        # 8. Pre-tax total
        pre_tax_total = net_cost + profit_total
        
        # 9. KDV
        kdv_total = pre_tax_total * kdv_rate
        
        # 10. Grand total (monthly tender price)
        grand_total_monthly = pre_tax_total + kdv_total
        
        # 11. Stamp tax (on contract value)
        contract_value = grand_total_monthly * contract_months
        stamp_tax = contract_value * stamp_tax_rate
        
        # 12. Final contract value
        final_contract = contract_value + stamp_tax
        
        return jsonify({
            # System data
            'system': {
                'total_employees': len(employees),
                'active_employees': active_employees,
                'vehicle_count': vehicle_count,
                'route_count': route_count,
                'total_distance_km': round(total_distance, 2),
                'total_duration_min': round(total_duration, 1),
                'daily_km': round(daily_km, 2),
                'monthly_km': round(monthly_km, 2),
            },
            # Parameters used
            'params': {
                'driver_salary': driver_gross_salary,
                'sgk_rate': round(sgk_employer_rate * 100, 2),
                'unemployment_rate': round(unemployment_rate * 100, 2),
                'vehicle_rent': vehicle_rent,
                'fuel_price': fuel_price_per_liter,
                'fuel_consumption': fuel_consumption,
                'maintenance': maintenance_monthly,
                'mtv': mtv_monthly,
                'working_days': working_days,
                'trips_per_day': trips_per_day,
                'overhead_rate': round(overhead_rate * 100, 2),
                'profit_rate': round(profit_rate * 100, 2),
                'kdv_rate': round(kdv_rate * 100, 2),
                'stamp_tax_rate': round(stamp_tax_rate * 100, 3),
                'contract_months': contract_months,
            },
            # Cost breakdown (monthly)
            'breakdown': {
                'driver': {
                    'gross_salary': round(driver_gross_salary, 2),
                    'sgk_per_driver': round(sgk_cost, 2),
                    'unemployment_per_driver': round(unemployment_cost, 2),
                    'total_per_driver': round(driver_total_per_vehicle, 2),
                    'total': round(driver_total, 2),
                },
                'vehicle': {
                    'rent_per_vehicle': round(vehicle_rent, 2),
                    'rent_total': round(vehicle_rent_total, 2),
                    'maintenance_per_vehicle': round(maintenance_monthly, 2),
                    'maintenance_total': round(maintenance_total, 2),
                    'mtv_per_vehicle': round(mtv_monthly, 2),
                    'mtv_total': round(mtv_total, 2),
                    'total': round(vehicle_total, 2),
                },
                'fuel': {
                    'liters_monthly': round(fuel_liters_monthly, 2),
                    'total': round(fuel_total, 2),
                },
                'subtotal': round(subtotal, 2),
                'overhead': round(overhead_total, 2),
                'net_cost': round(net_cost, 2),
                'profit': round(profit_total, 2),
                'pre_tax_total': round(pre_tax_total, 2),
                'kdv': round(kdv_total, 2),
                'grand_total_monthly': round(grand_total_monthly, 2),
            },
            # Contract summary
            'contract': {
                'months': int(contract_months),
                'monthly_total': round(grand_total_monthly, 2),
                'contract_value': round(contract_value, 2),
                'stamp_tax': round(stamp_tax, 2),
                'final_total': round(final_contract, 2),
                'per_employee_monthly': round(grand_total_monthly / active_employees, 2) if active_employees else 0,
                'per_vehicle_monthly': round(grand_total_monthly / vehicle_count, 2) if vehicle_count else 0,
                'per_km': round(grand_total_monthly / monthly_km, 2) if monthly_km else 0,
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
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
