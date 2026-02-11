"""
Service classes for the route optimization system.

Contains: LocationService, ClusteringService, RoutingService, 
          VisualizationService, ZoneService, ServicePlanner
"""
from __future__ import annotations

import hashlib
import math
import os
import random
from datetime import datetime, timedelta

import folium
import numpy as np
from shapely.geometry import Point, box, MultiLineString, LineString
from shapely.ops import unary_union, polygonize
from pyrosm import OSM

from models import Employee, Cluster, Route, Vehicle
from utils import DataGenerator, KMeansClusterer
from routing import OSRMRouter


# =============================================================================
# Location Service
# =============================================================================

class LocationService:
    """Service for generating and managing employee locations."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.data_generator = DataGenerator(osm_file=config.OSM_FILE)
    
    def generate_employees(self, count: int, seed: int | None = None) -> list[Employee]:
        df = self.data_generator.generate(n=count, seed=seed)
        return [Employee(id=int(row['id']), lat=row['lat'], lon=row['lon']) 
                for _, row in df.iterrows()]
    
    def get_transit_stops(self) -> list[tuple[float, float]]:
        return self.data_generator.get_transit_stops()


# =============================================================================
# Clustering Service
# =============================================================================

class ClusteringService:
    """Service for clustering employees into groups."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.clusterer: KMeansClusterer | None = None
    
    def cluster_employees(self, employees: list[Employee], num_clusters: int, random_state: int | None = None) -> list[Cluster]:
        self.clusterer = KMeansClusterer(n_clusters=num_clusters, random_state=random_state)
        coords = np.array([[e.lat, e.lon] for e in employees])
        self.clusterer.fit(coords)
        
        clusters = [Cluster(id=i, center=tuple(self.clusterer.cluster_centers_[i])) 
                    for i in range(num_clusters)]
        for emp, cid in zip(employees, self.clusterer.labels_):
            clusters[cid].add_employee(emp)
        return clusters
    
    def cluster_by_zones(self, zone_assignments: dict, employees_per_cluster: int = 20, random_state: int | None = None) -> list[Cluster]:
        clusters = []
        gid = 0
        
        for zone_id, zone_emps in zone_assignments.items():
            if not zone_emps:
                continue
            n = len(zone_emps)
            n_clusters = max(1, min(n, math.ceil(n / employees_per_cluster)))

            
            if n_clusters == 1:
                center = (sum(e.lat for e in zone_emps)/n, sum(e.lon for e in zone_emps)/n)
                c = Cluster(id=gid, center=center)
                c.zone_id = zone_id
                for e in zone_emps:
                    c.add_employee(e)
                clusters.append(c)
                gid += 1
            else:
                km = KMeansClusterer(n_clusters=n_clusters, random_state=random_state)
                km.fit(np.array([[e.lat, e.lon] for e in zone_emps]))
                zone_clusters = []
                for i in range(n_clusters):
                    c = Cluster(id=gid, center=tuple(km.cluster_centers_[i]))
                    c.zone_id = zone_id
                    zone_clusters.append(c)
                    gid += 1
                for emp, idx in zip(zone_emps, km.labels_):
                    zone_clusters[idx].add_employee(emp)
                clusters.extend(zone_clusters)
        return clusters
    
    def snap_centers_to_roads(self, clusters: list[Cluster]) -> int:
        router = OSRMRouter()
        count = 0
        for c in clusters:
            result = router.snap_to_road(c.center[0], c.center[1])
            if result:
                c.original_center = c.center
                c.center = (result['lat'], result['lon'])
                count += 1

        return count
    
    def enforce_capacity_constraints(self, clusters: list[Cluster], capacity: int) -> list[Cluster]:
        new_clusters = []
        next_id = max(c.id for c in clusters) + 1
        
        for c in clusters:
            active = c.get_employee_count(include_excluded=False)
            if active <= capacity:
                new_clusters.append(c)
            else:
                n_splits = math.ceil(active / capacity)

                active_emps = c.get_active_employees()
                
                km = KMeansClusterer(n_clusters=n_splits, random_state=42)
                km.fit(np.array([[e.lat, e.lon] for e in active_emps]))
                
                subs = [Cluster(id=next_id+i, center=tuple(km.cluster_centers_[i])) for i in range(n_splits)]
                for s in subs:
                    s.zone_id = getattr(c, 'zone_id', None)
                    s.parent_cluster_id = c.id
                
                for emp, idx in zip(active_emps, km.labels_):
                    subs[idx].add_employee(emp)
                
                for e in c.employees:
                    if e.excluded:
                        nearest = min(subs, key=lambda s: e.distance_to(*s.center))
                        nearest.add_employee(e)
                
                new_clusters.extend(subs)
                next_id += n_splits
        return new_clusters
    
    def validate_capacity(self, clusters: list[Cluster], capacity: int) -> tuple[bool, list]:
        violations = [{'cluster_id': c.id, 'count': c.get_employee_count(False)} 
                      for c in clusters if c.get_employee_count(False) > capacity]
        return len(violations) == 0, violations


# =============================================================================
# Routing Service
# =============================================================================

class RoutingService:
    """Service for optimizing vehicle routes."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.osrm_router = OSRMRouter()
    
    def optimize_cluster_route(self, cluster: Cluster, use_stops: bool = True) -> Route | None:
        stops = cluster.stops if use_stops and cluster.has_stops() else cluster.get_employee_locations(False)

        
        if not stops:
            return None
        
        route = Route(cluster=cluster)
        route.set_stops(stops)
        
        try:
            data = self.osrm_router.get_route(stops)
            route.coordinates = data['coordinates']
            route.distance_km = data['distance_km']
            route.duration_min = data['duration_min']
        except Exception:
            route.calculate_stats_from_stops()
        
        cluster.assign_route(route)
        return route


# =============================================================================
# Visualization Service
# =============================================================================

class VisualizationService:
    """Service for creating map visualizations."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.colors: dict[int, str] = {}
    
    def _color(self, id: int) -> str:
        if id not in self.colors:
            random.seed(int(hashlib.md5(f"c{id}".encode()).hexdigest(), 16))
            h = int((id * 0.618 * 360) % 360 + random.randint(-30, 30)) % 360
            self.colors[id] = f'hsl({h}, {random.randint(65,95)}%, {random.randint(40,70)}%)'
        return self.colors[id]
    
    def create_employees_map(self, employees: list[Employee]) -> str:
        fn = "maps/employees.html"
        if not employees:
            return fn
        m = folium.Map(location=[sum(e.lat for e in employees)/len(employees), 
                                  sum(e.lon for e in employees)/len(employees)], zoom_start=12)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        for e in employees:
            folium.CircleMarker([e.lat, e.lon], radius=4, color='#2563eb', fill=True).add_to(m)
        m.save(fn)
        return fn
    
    def create_clusters_map(self, clusters: list[Cluster]) -> str:
        fn = "maps/clusters.html"
        all_emps = [e for c in clusters for e in c.employees]
        if not all_emps:
            return fn
        m = folium.Map(location=[sum(e.lat for e in all_emps)/len(all_emps), 
                                  sum(e.lon for e in all_emps)/len(all_emps)], zoom_start=12)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        for c in clusters:
            folium.Marker(c.center, popup=f"Cluster {c.id}", icon=folium.Icon(color='black', icon='star', prefix='fa')).add_to(m)
        for e in all_emps:
            folium.CircleMarker([e.lat, e.lon], radius=5, color=self._color(e.cluster_id), fill=True).add_to(m)
        m.save(fn)
        return fn
    
    def create_routes_map(self, clusters: list[Cluster]) -> str:
        fn = "maps/optimized_routes.html"
        m = folium.Map(location=self.office_location, zoom_start=11)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        
        for c in clusters:
            if not c.route:
                continue
            color = self._color(c.id)
            if c.route.coordinates:
                folium.PolyLine(c.route.coordinates, color=color, weight=4, opacity=0.7).add_to(m)
            for e in c.get_active_employees():
                folium.CircleMarker(e.get_location(), radius=3, color=color, fill=True).add_to(m)
            folium.Marker(c.center, icon=folium.DivIcon(html=f'<div style="background:{color};color:white;padding:5px;border-radius:50%;width:30px;height:30px;text-align:center;line-height:30px;font-weight:bold;border:3px solid white">{c.id}</div>')).add_to(m)
        m.save(fn)
        return fn
    
    def create_cluster_detail_map(self, cluster: Cluster) -> str:
        os.makedirs("maps/detailed", exist_ok=True)
        fn = f"maps/detailed/cluster_{cluster.id}_detail.html"
        m = folium.Map(location=cluster.center, zoom_start=14)
        color = self._color(cluster.id)
        
        # Office marker
        folium.Marker(self.office_location, popup="<b>Office</b>", 
                      icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        
        # Cluster center
        folium.Marker(cluster.center, popup=f"<b>Cluster {cluster.id} Center</b>", 
                      icon=folium.Icon(color='black', icon='star', prefix='fa')).add_to(m)
        
        # Track unique pickup points to draw bus stop markers
        pickup_points_drawn = set()
        
        # Employees with pickup lines
        for employee in cluster.employees:
            if employee.excluded:
                folium.CircleMarker(
                    location=employee.get_location(), radius=4, color='gray',
                    fill=True, fillColor='lightgray', fillOpacity=0.5,
                    popup=f"<b>ID:</b> {employee.id}<br><b>Status:</b> Excluded<br><b>Reason:</b> {employee.exclusion_reason}"
                ).add_to(m)
            else:
                # Get pickup point
                target_location = employee.pickup_point if hasattr(employee, 'pickup_point') and employee.pickup_point else None
                
                if target_location:
                    walk_distance = employee.distance_to(target_location[0], target_location[1])
                    
                    # Draw walking line (dashed)
                    folium.PolyLine(
                        [employee.get_location(), target_location],
                        color=color, weight=1.5, opacity=0.6, dash_array='5, 5',
                        popup=f"Walk: {walk_distance:.0f}m"
                    ).add_to(m)
                    
                    # Walking distance label at midpoint
                    midpoint = [(employee.lat + target_location[0]) / 2, (employee.lon + target_location[1]) / 2]
                    folium.Marker(
                        location=midpoint,
                        icon=folium.DivIcon(icon_size=(80, 20), icon_anchor=(40, 10), html=f'''
                            <div style="font-size: 10px; color: {color}; font-weight: bold; 
                                 background: rgba(255,255,255,0.8); padding: 1px 4px; border-radius: 3px;
                                 text-align: center;">{walk_distance:.0f}m</div>
                        ''')
                    ).add_to(m)
                    
                    # Draw bus stop marker (only once per unique location)
                    stop_key = (round(target_location[0], 6), round(target_location[1], 6))
                    
                    if stop_key not in pickup_points_drawn:
                        folium.Marker(
                            location=target_location,
                            icon=folium.DivIcon(
                                html='<div style="font-size: 18px; color: green; text-shadow: 1px 1px 2px white;"><i class="fa fa-bus"></i></div>',
                                icon_size=(20, 20), icon_anchor=(10, 10)
                            ),
                            popup="Pickup Stop"
                        ).add_to(m)
                        pickup_points_drawn.add(stop_key)
                
                # Employee marker
                folium.CircleMarker(
                    location=employee.get_location(), radius=5, color=color,
                    fill=True, fillColor=color, fillOpacity=0.7,
                    popup=f"<b>ID:</b> {employee.id}", weight=2
                ).add_to(m)
        
        # Route polyline
        if cluster.route and cluster.route.coordinates:
            folium.PolyLine(cluster.route.coordinates, color=color, weight=5, opacity=0.8,
                           popup=f"<b>Route</b><br>{cluster.route.distance_km:.1f} km<br>{cluster.route.duration_min:.0f} min").add_to(m)
        
        m.save(fn)
        return fn
    
    def create_editable_cluster_map(self, cluster: Cluster) -> str:
        """Create an interactive map with draggable route editing using Leaflet Routing Machine."""
        import json
        
        os.makedirs("maps/editable", exist_ok=True)
        fn = f"maps/editable/cluster_{cluster.id}_edit.html"
        color = self._color(cluster.id)
        
        # Get waypoints: pickup stops or employee locations
        waypoints = []
        if cluster.stops:
            waypoints = list(cluster.stops)
        elif cluster.route and cluster.route.stops:
            waypoints = list(cluster.route.stops)
        else:
            # Fallback to employee locations + cluster center + office
            for emp in cluster.get_active_employees():
                waypoints.append(emp.get_location())
            waypoints.append(cluster.center)
            waypoints.append(self.office_location)
        
        # Generate JavaScript array of L.latLng calls - proper JavaScript code, not strings
        waypoints_js = "[" + ", ".join([f"L.latLng({float(wp[0])}, {float(wp[1])})" for wp in waypoints]) + "]"
        
        # Employee data for markers - convert to JSON-safe format
        employees_data = []
        for emp in cluster.employees:
            pickup = None
            if hasattr(emp, 'pickup_point') and emp.pickup_point:
                pickup = [float(emp.pickup_point[0]), float(emp.pickup_point[1])]
            employees_data.append({
                'lat': float(emp.lat),
                'lon': float(emp.lon),
                'id': int(emp.id),
                'excluded': bool(emp.excluded),
                'pickup_point': pickup
            })
        
        # Convert to JSON string for JavaScript
        employees_json = json.dumps(employees_data)
        
        # Generate the HTML with Leaflet Routing Machine
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Route - Cluster {cluster.id}</title>
    
    <!-- Leaflet CSS & JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <!-- Leaflet Routing Machine CSS & JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.css" />
    <script src="https://unpkg.com/leaflet-routing-machine@3.2.12/dist/leaflet-routing-machine.js"></script>
    
    <!-- Font Awesome for icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    
    <style>
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        #map {{
            height: calc(100% - 60px);
            width: 100%;
        }}
        .toolbar {{
            height: 60px;
            background: #667eea;
            display: flex;
            align-items: center;
            padding: 0 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        .toolbar h1 {{
            color: white;
            font-size: 18px;
            margin: 0;
            flex: 1;
        }}
        .toolbar button {{
            background: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            margin-left: 10px;
            transition: all 0.2s;
        }}
        .toolbar button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        .toolbar button.primary {{
            background: #10b981;
            color: white;
        }}
        .toolbar button.secondary {{
            background: #f3f4f6;
            color: #374151;
        }}
        .info-panel {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 15px 20px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            max-width: 300px;
        }}
        .info-panel h3 {{
            margin: 0 0 10px 0;
            color: #1f2937;
        }}
        .info-panel p {{
            margin: 5px 0;
            color: #6b7280;
            font-size: 14px;
        }}
        .info-panel .stat {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #e5e7eb;
        }}
        .info-panel .stat:last-child {{
            border-bottom: none;
        }}
        .info-panel .stat-value {{
            font-weight: 600;
            color: #1f2937;
        }}
        .leaflet-routing-container {{
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .employee-marker {{
            background: {color};
            border: 2px solid white;
            border-radius: 50%;
            width: 12px;
            height: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        .excluded-marker {{
            background: #9ca3af;
            border: 2px solid white;
            border-radius: 50%;
            width: 10px;
            height: 10px;
            opacity: 0.6;
        }}
        .toast {{
            position: fixed;
            bottom: 80px;
            right: 20px;
            background: #1f2937;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 2000;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s;
        }}
        .toast.show {{
            opacity: 1;
            transform: translateY(0);
        }}
    </style>
</head>
<body>
    <div class="toolbar">
        <h1><i class="fas fa-route"></i> Cluster {cluster.id} - Route Editor</h1>
        <button class="secondary" onclick="resetRoute()"><i class="fas fa-undo"></i> Reset</button>
        <button class="secondary" onclick="addWaypoint()"><i class="fas fa-plus"></i> Add Stop</button>
        <button class="primary" onclick="exportRoute()"><i class="fas fa-download"></i> Export Route</button>
    </div>
    
    <div id="map"></div>
    
    <div class="info-panel">
        <h3><i class="fas fa-info-circle"></i> Route Info</h3>
        <div class="stat">
            <span>Distance:</span>
            <span class="stat-value" id="distance">--</span>
        </div>
        <div class="stat">
            <span>Duration:</span>
            <span class="stat-value" id="duration">--</span>
        </div>
        <div class="stat">
            <span>Waypoints:</span>
            <span class="stat-value" id="waypoints">--</span>
        </div>
        <p style="margin-top: 10px; font-size: 12px; color: #9ca3af;">
            <i class="fas fa-hand-pointer"></i> Drag markers to edit route
        </p>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        // Initialize map
        const map = L.map('map').setView([{float(cluster.center[0])}, {float(cluster.center[1])}], 14);
        
        // Add tile layer
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);
        
        // Initial waypoints as L.latLng objects
        const initialWaypoints = {waypoints_js};
        
        // Store original waypoints for reset (deep copy)
        const originalWaypoints = initialWaypoints.map(wp => L.latLng(wp.lat, wp.lng));
        
        // Employee data
        const employees = {employees_json};
        
        // Office location
        const officeLocation = [{float(self.office_location[0])}, {float(self.office_location[1])}];
        
        // Create routing control with local OSRM server
        let routingControl = L.Routing.control({{
            router: L.Routing.osrmv1({{
                serviceUrl: 'http://localhost:5001/route/v1'
            }}),
            waypoints: initialWaypoints,
            routeWhileDragging: true,
            draggableWaypoints: true,
            addWaypoints: true,
            fitSelectedRoutes: true,
            showAlternatives: false,
            lineOptions: {{
                styles: [{{
                    color: '{color}',
                    opacity: 0.8,
                    weight: 6
                }}],
                extendToWaypoints: true,
                missingRouteTolerance: 0
            }},
            createMarker: function(i, waypoint, n) {{
                const isOffice = (waypoint.latLng.lat.toFixed(4) === officeLocation[0].toFixed(4) && 
                                  waypoint.latLng.lng.toFixed(4) === officeLocation[1].toFixed(4));
                
                if (isOffice) {{
                    return L.marker(waypoint.latLng, {{
                        draggable: true,
                        icon: L.divIcon({{
                            className: 'custom-marker',
                            html: '<div style="font-size: 24px; color: #dc2626;"><i class="fas fa-home"></i></div>',
                            iconSize: [30, 30],
                            iconAnchor: [15, 15]
                        }})
                    }}).bindPopup('<b>Office</b>');
                }}
                
                return L.marker(waypoint.latLng, {{
                    draggable: true,
                    icon: L.divIcon({{
                        className: 'custom-marker',
                        html: '<div style="background: #10b981; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">' + (i + 1) + '</div>',
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    }})
                }}).bindPopup('<b>Stop ' + (i + 1) + '</b><br>Drag to move');
            }}
        }}).addTo(map);
        
        // Add employee markers
        employees.forEach(emp => {{
            const markerClass = emp.excluded ? 'excluded-marker' : 'employee-marker';
            const marker = L.marker([emp.lat, emp.lon], {{
                icon: L.divIcon({{
                    className: markerClass,
                    html: emp.excluded 
                        ? '<div class="excluded-marker"></div>'
                        : '<div class="employee-marker"></div>',
                    iconSize: [12, 12],
                    iconAnchor: [6, 6]
                }})
            }}).addTo(map);
            
            let popupContent = '<b>Employee ID: ' + emp.id + '</b>';
            if (emp.excluded) {{
                popupContent += '<br><span style="color: #9ca3af;">Excluded</span>';
            }}
            if (emp.pickup_point) {{
                popupContent += '<br>Pickup: ' + emp.pickup_point[0].toFixed(5) + ', ' + emp.pickup_point[1].toFixed(5);
            }}
            marker.bindPopup(popupContent);
        }});
        
        // Update info panel when route changes
        routingControl.on('routesfound', function(e) {{
            const routes = e.routes;
            const summary = routes[0].summary;
            
            document.getElementById('distance').textContent = (summary.totalDistance / 1000).toFixed(2) + ' km';
            document.getElementById('duration').textContent = Math.round(summary.totalTime / 60) + ' min';
            document.getElementById('waypoints').textContent = routingControl.getWaypoints().filter(wp => wp.latLng).length;
        }});
        
        // Toast notification
        function showToast(message) {{
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}
        
        // Reset route to original waypoints
        function resetRoute() {{
            routingControl.setWaypoints(originalWaypoints);
            showToast('Route reset to original');
        }}
        
        // Add a new waypoint at map center
        function addWaypoint() {{
            const center = map.getCenter();
            const waypoints = routingControl.getWaypoints();
            const newWaypoints = [...waypoints.slice(0, -1), L.latLng(center.lat, center.lng), waypoints[waypoints.length - 1]];
            routingControl.setWaypoints(newWaypoints.map(wp => wp.latLng || wp));
            showToast('New waypoint added at map center');
        }}
        
        // Export route as JSON
        function exportRoute() {{
            const waypoints = routingControl.getWaypoints()
                .filter(wp => wp.latLng)
                .map(wp => ({{lat: wp.latLng.lat, lon: wp.latLng.lng}}));
            
            const routeData = {{
                cluster_id: {cluster.id},
                waypoints: waypoints,
                exported_at: new Date().toISOString()
            }};
            
            const blob = new Blob([JSON.stringify(routeData, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'cluster_{cluster.id}_route.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showToast('Route exported successfully!');
            console.log('Exported route:', routeData);
        }}
    </script>
</body>
</html>'''
        
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return fn

    
    def create_zones_map(self, clusters: list[Cluster], zones=None, barrier_roads=None) -> str:
        fn = "maps/zones.html"
        all_emps = [e for c in clusters for e in c.employees]
        if not all_emps:
            return fn
        m = folium.Map(location=[sum(e.lat for e in all_emps)/len(all_emps), 
                                  sum(e.lon for e in all_emps)/len(all_emps)], zoom_start=12)
        folium.Marker(self.office_location, popup="Office", icon=folium.Icon(color='red', icon='home', prefix='fa')).add_to(m)
        
        if zones:
            for i, z in enumerate(zones):
                try:
                    if hasattr(z, 'exterior'):
                        folium.Polygon([[c[1], c[0]] for c in z.exterior.coords], color='#333', weight=2, fill=True, fill_opacity=0.1).add_to(m)
                except:
                    pass
        
        if barrier_roads:
            try:
                lines = barrier_roads.geoms if hasattr(barrier_roads, 'geoms') else [barrier_roads]
                for line in lines:
                    if hasattr(line, 'coords'):
                        folium.PolyLine([[c[1], c[0]] for c in line.coords], color='#dc2626', weight=4, opacity=0.8).add_to(m)
            except:
                pass
        
        for e in all_emps:
            folium.CircleMarker([e.lat, e.lon], radius=4, color=self._color(getattr(e, 'zone_id', 0)*10), fill=True).add_to(m)
        m.save(fn)
        return fn
    
    def create_all_maps(self, clusters: list[Cluster], zones=None, barrier_roads=None) -> list[str]:
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        all_emps = [e for c in clusters for e in c.employees]
        files = [self.create_employees_map(all_emps), self.create_clusters_map(clusters), self.create_routes_map(clusters)]
        if zones or barrier_roads:
            files.append(self.create_zones_map(clusters, zones, barrier_roads))
        for c in clusters:
            if c.route:  # Only create detailed maps for clusters with routes
                files.append(self.create_cluster_detail_map(c))
                files.append(self.create_editable_cluster_map(c))  # Also create editable version
        return files


# =============================================================================
# Zone Service
# =============================================================================

class ZoneService:
    """Service for creating walkable zones based on road barriers."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.osm_file = getattr(config, 'OSM_FILE', 'data/istanbul-center.osm.pbf')
        self.barrier_types = getattr(config, 'BARRIER_ROAD_TYPES', 
                                     ['motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary'])
        self._osm = None
        self._barrier_roads = None
        self._zones = []
        self._stats = {}
    
    def _load_osm(self) -> None:
        if self._osm is None:
            self._osm = OSM(self.osm_file)
    
    def load_barrier_roads(self):
        self._load_osm()

        roads = self._osm.get_data_by_custom_criteria(
            custom_filter={"highway": self.barrier_types},
            filter_type="keep", keep_nodes=False, keep_ways=True, keep_relations=False
        )
        if roads is None or len(roads) == 0:

            return None
        self._barrier_roads = unary_union(roads.geometry)

        return self._barrier_roads
    
    def create_zones(self, employees: list[Employee]):
        if self._barrier_roads is None:
            self.load_barrier_roads()
        if self._barrier_roads is None:
            return []
        
        lats, lons = [e.lat for e in employees], [e.lon for e in employees]
        padding = 0.01
        bounds = box(min(lons)-padding, min(lats)-padding, max(lons)+padding, max(lats)+padding)
        clipped = self._barrier_roads.intersection(bounds)
        
        all_lines = unary_union([clipped, bounds.boundary]) if isinstance(clipped, (LineString, MultiLineString)) else bounds.boundary
        zones = [z for z in polygonize(all_lines) if z.area > 0.00001]
        self._zones = zones

        return zones
    
    def assign_employees_to_zones(self, employees: list[Employee]) -> dict:
        if not self._zones:
            self.create_zones(employees)
        
        assignments = {i: [] for i in range(len(self._zones))}
        for e in employees:
            pt = Point(e.lon, e.lat)
            assigned = False
            for i, z in enumerate(self._zones):
                if z.contains(pt):
                    e.zone_id = i
                    assignments[i].append(e)
                    assigned = True
                    break
            if not assigned:
                nearest = min(range(len(self._zones)), key=lambda i: self._zones[i].boundary.distance(pt))
                e.zone_id = nearest
                assignments[nearest].append(e)
        
        self._stats = {'total_zones': len(self._zones), 'empty_zones': sum(1 for v in assignments.values() if not v)}
        assignments = {k: v for k, v in assignments.items() if v}

        return assignments
    
    def get_zones(self):
        return self._zones
    
    def get_zone_stats(self):
        return self._stats
    
    def get_barrier_roads(self):
        return self._barrier_roads


# =============================================================================
# Service Planner (Main Orchestrator)
# =============================================================================

class ServicePlanner:
    """Main orchestrator for route optimization."""
    
    def __init__(self, config) -> None:
        self.config = config
        self.employees: list[Employee] = []
        self.clusters: list[Cluster] = []
        self.vehicles: list[Vehicle] = []
        self.location_service = LocationService(config)
        self.clustering_service = ClusteringService(config)
        self.routing_service = RoutingService(config)
        self.visualization_service = VisualizationService(config)
        self.zone_service = ZoneService(config) if getattr(config, 'USE_ZONE_PARTITIONING', False) else None
        self.stats = {}
        self.zone_assignments = {}
        self.safe_stops = []
        self.all_employees: list[Employee] = []  # Includes excluded (for DB save)
        
        # Database integration
        self.use_database = getattr(config, 'USE_DATABASE', False)
        self.db = None
        self.zone_repo = None
        self.employee_repo = None
        self.cluster_repo = None
        self.route_repo = None
        self.vehicle_repo = None
        
        if self.use_database:
            self._init_database()
    
    @staticmethod
    def get_departure_time() -> datetime:
        t = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        return t + timedelta(days=1) if datetime.now().hour >= 8 else t
    
    def generate_employees(self, count: int | None = None, seed: int | None = None) -> list[Employee]:
        """Generate new employees or load from database if configured."""
        # Try to load from database if configured
        load_from_db = getattr(self.config, 'LOAD_EMPLOYEES_FROM_DB', True)
        if load_from_db and self.use_database and self.employee_repo:
            db_employees = self.load_employees_from_db()
            if db_employees:
                return db_employees
        
        # Generate new employees
        count = count or self.config.NUM_EMPLOYEES
        seed = seed if seed is not None else 42
        print(f"[1] Generating {count} employee locations...")
        self.employees = self.location_service.generate_employees(count, seed)
        # For new employees, all are active, so all_employees = employees
        self.all_employees = list(self.employees)
        print(f"    OK: {len(self.employees)} employees generated")
        return self.employees
    
    def load_employees_from_db(self) -> list[Employee]:
        """Load existing employees from database."""
        if not self.employee_repo:
            return []
        
        print("[1] Loading employees from database...")
        all_employees = self.employee_repo.find_all()
        
        if not all_employees:
            print("    No employees in database, will generate new ones")
            return []
        
        # Clear old zone_id and cluster_id since zones/clusters are regenerated
        for emp in all_employees:
            emp.zone_id = None
            emp.cluster_id = None
        
        # Store ALL employees (for saving back to DB with updated data)
        self.all_employees = all_employees
        
        # But only use active (non-excluded) employees for routing
        self.employees = [e for e in all_employees if not e.excluded]
        excluded_count = len(all_employees) - len(self.employees)
        
        print(f"    OK: {len(self.employees)} active employees loaded ({excluded_count} excluded)")
        return self.employees
    
    def create_zones(self) -> dict:
        if not self.zone_service:
            print("[2a] Zone partitioning (DISABLED)...")
            return {}
        print("[2a] Creating zones from road barriers...")
        self.zone_service.load_barrier_roads()
        self.zone_service.create_zones(self.employees)
        self.zone_assignments = self.zone_service.assign_employees_to_zones(self.employees)
        stats = self.zone_service.get_zone_stats()
        print(f"    OK: {stats['total_zones']} zones created, {len(self.zone_assignments)} non-empty")
        return self.zone_assignments
    
    def create_clusters(self, num_clusters: int | None = None) -> list[Cluster]:
        if self.zone_assignments:
            epc = getattr(self.config, 'EMPLOYEES_PER_CLUSTER', 20)
            print(f"[2b] Creating zone-aware clusters (~{epc} employees each)...")
            self.clusters = self.clustering_service.cluster_by_zones(self.zone_assignments, epc, 42)
        else:
            num_clusters = num_clusters or self.config.NUM_CLUSTERS
            print(f"[2b] Creating {num_clusters} clusters...")
            self.clusters = self.clustering_service.cluster_employees(self.employees, num_clusters, 42)
        print(f"    OK: {len(self.clusters)} clusters created")
        
        print("[2c] Snapping cluster centers to roads...")
        snapped = self.clustering_service.snap_centers_to_roads(self.clusters)
        print(f"    OK: {snapped}/{len(self.clusters)} snapped")
        
        cap = getattr(self.config, 'VEHICLE_CAPACITY', 50)
        print(f"[2d] Enforcing capacity (max {cap})...")
        valid, violations = self.clustering_service.validate_capacity(self.clusters, cap)
        if not valid:
            print(f"    {len(violations)} over capacity, splitting...")
            self.clusters = self.clustering_service.enforce_capacity_constraints(self.clusters, cap)
        print(f"    OK: {len(self.clusters)} clusters")
        return self.clusters
    
    def generate_stops(self) -> dict:
        print("[3] Finding farthest employees from office...")
        office_lat, office_lon = self.config.OFFICE_LOCATION
        count = 0
        for c in self.clusters:
            active = c.get_active_employees()
            if not active:
                continue
            farthest = max(active, key=lambda e: e.distance_to(office_lat, office_lon))
            c.set_stops([farthest.get_location(), c.center, self.config.OFFICE_LOCATION],
                       [0]*len(active) + [1, 2], [len(active), 0, 0])
            count += 1
        print(f"    OK: {count} routes created")
        return {'total_routes': count}
    
    def optimize_routes(self, use_stops: bool = True) -> list[Route]:
        min_emp = getattr(self.config, 'MIN_EMPLOYEES_FOR_SHUTTLE', 10)
        print(f"[4] Creating routes (min {min_emp} employees)...")
        routes, skipped = [], 0
        for c in self.clusters:
            if c.get_employee_count(False) < min_emp:
                skipped += 1
                continue
            route = self.routing_service.optimize_cluster_route(c, use_stops)
            if route:
                routes.append(route)
        
        print(f"    OK: {len(routes)} routes, {skipped} clusters skipped")
        
        for c in self.clusters:
            if c.route:
                discovery_buffer = getattr(self.config, 'BUS_STOP_DISCOVERY_BUFFER_METERS', 150)
                same_side = getattr(self.config, 'FILTER_STOPS_BY_ROUTE_SIDE', True)
                c.route.find_all_stops_along_route(self.safe_stops, buffer_meters=discovery_buffer, same_side_only=same_side)
                stop_buffer = getattr(self.config, 'ROUTE_STOP_BUFFER_METERS', 15)
                c.route.match_employees_to_route(c.employees, self.safe_stops, buffer_meters=stop_buffer)
        
        total_bus_stops = sum(len(c.route.bus_stops) for c in self.clusters if c.route)
        print(f"    Bus stops found along routes: {total_bus_stops}")
        
        return routes
    
    def reassign_employees_to_closer_routes(self) -> dict:
        """
        Reassign employees to stops on other clusters' routes if closer.
        
        For employees whose walking distance exceeds MAX_WALK_DISTANCE,
        check if there's a closer stop on another cluster's route and
        reassign them to that cluster.
        
        Returns dict with reassignment statistics.
        """
        max_walk = getattr(self.config, 'MAX_WALK_DISTANCE', 500)  # meters
        print(f"[4b] Cross-cluster reassignment (max walk: {max_walk}m)...")
        
        # Collect all stops from all routes with their cluster IDs
        all_route_stops = []  # [(lat, lon, cluster_id, cluster), ...]
        for cluster in self.clusters:
            if not cluster.route or not cluster.route.stops:
                continue
            for stop in cluster.route.stops:
                all_route_stops.append((stop[0], stop[1], cluster.id, cluster))
        
        if not all_route_stops:
            print("    No route stops available for reassignment")
            return {'reassigned': 0, 'checked': 0}
        
        # Find employees with excessive walking distance
        reassigned_count = 0
        checked_count = 0
        reassignments = []  # Track for logging
        
        for cluster in self.clusters:
            employees_to_remove = []
            
            for employee in cluster.get_active_employees():
                # Skip if no pickup point assigned
                if not employee.pickup_point:
                    continue
                
                current_walk_distance = employee.walking_distance
                if current_walk_distance is None:
                    # Calculate if not set
                    current_walk_distance = employee.distance_to(
                        employee.pickup_point[0], employee.pickup_point[1]
                    )
                
                # Only check employees with excessive walking distance
                if current_walk_distance <= max_walk:
                    continue
                
                checked_count += 1
                
                # Find the closest stop from any route (including other clusters)
                best_stop = None
                best_distance = current_walk_distance
                best_cluster = None
                
                for stop_lat, stop_lon, stop_cluster_id, stop_cluster in all_route_stops:
                    # Calculate walking distance to this stop
                    dist = employee.distance_to(stop_lat, stop_lon)
                    
                    if dist < best_distance:
                        best_distance = dist
                        best_stop = (stop_lat, stop_lon)
                        best_cluster = stop_cluster
                
                # Reassign if a better stop was found on a different cluster
                if best_stop and best_cluster and best_cluster.id != cluster.id:
                    # Check if new distance is acceptable
                    if best_distance <= max_walk or best_distance < current_walk_distance * 0.7:
                        # Mark for removal from current cluster
                        employees_to_remove.append((employee, best_cluster, best_stop, best_distance))
                        reassignments.append({
                            'employee_id': employee.id,
                            'from_cluster': cluster.id,
                            'to_cluster': best_cluster.id,
                            'old_distance': current_walk_distance,
                            'new_distance': best_distance
                        })
            
            # Perform reassignments
            for employee, new_cluster, new_stop, new_distance in employees_to_remove:
                # Remove from old cluster
                cluster.employees.remove(employee)
                
                # Add to new cluster
                new_cluster.add_employee(employee)
                
                # Update pickup point
                employee.set_pickup_point(
                    new_stop[0], new_stop[1], 
                    type="stop", 
                    walking_distance=new_distance
                )
                
                reassigned_count += 1
        
        # Log results
        if reassigned_count > 0:
            print(f"    ✓ Reassigned {reassigned_count} employees to closer routes")
            for r in reassignments[:5]:  # Show first 5
                print(f"      Employee {r['employee_id']}: Cluster {r['from_cluster']} → {r['to_cluster']} "
                      f"({r['old_distance']:.0f}m → {r['new_distance']:.0f}m)")
            if len(reassignments) > 5:
                print(f"      ... and {len(reassignments) - 5} more")
        else:
            print(f"    ✓ No employees needed reassignment ({checked_count} checked)")
        
        return {
            'reassigned': reassigned_count,
            'checked': checked_count,
            'details': reassignments
        }
    
    def assign_vehicles(self) -> list[Vehicle]:
        cap = getattr(self.config, 'VEHICLE_CAPACITY', 50)
        vtype = getattr(self.config, 'VEHICLE_TYPE', 'Minibus')
        print(f"[5] Assigning vehicles (capacity: {cap})...")
        self.vehicles = []
        for i, c in enumerate(self.clusters):
            v = Vehicle(id=i+1, capacity=cap, vehicle_type=vtype)
            v.assign_cluster(c)
            v.set_departure_time(self.get_departure_time())
            c.assign_vehicle(v)
            self.vehicles.append(v)
        print(f"    OK: {len(self.vehicles)} vehicles")
        return self.vehicles
    
    def generate_maps(self) -> list[str]:
        print("[6] Generating maps...")
        zones = barrier_roads = None
        if self.zone_service:
            zones = self.zone_service.get_zones()
            barrier_roads = self.zone_service.get_barrier_roads()
        files = self.visualization_service.create_all_maps(self.clusters, zones, barrier_roads)
        print(f"    OK: {len(files)} maps created")
        return files
    
    def calculate_statistics(self) -> dict:
        total = len(self.employees)
        excluded = sum(1 for e in self.employees if e.excluded)
        dist = sum(c.route.distance_km for c in self.clusters if c.route)
        dur = sum(c.route.duration_min for c in self.clusters if c.route)
        self.stats = {
            'total_employees': total, 'active_employees': total-excluded,
            'excluded_employees': excluded, 'num_clusters': len(self.clusters),
            'num_vehicles': len(self.vehicles), 'total_distance_km': round(dist, 2),
            'total_duration_min': round(dur, 1)
        }
        return self.stats
    
    def print_summary(self) -> None:
        s = self.calculate_statistics()
        print("\n" + "="*50 + "\n                    SUMMARY\n" + "="*50)
        print(f"✓ Total Employees: {s['total_employees']}\n✓ Active: {s['active_employees']}\n✓ Excluded: {s['excluded_employees']}")
        print(f"✓ Clusters: {s['num_clusters']}\n✓ Vehicles: {s['num_vehicles']}")
        print(f"✓ Distance: {s['total_distance_km']} km\n✓ Duration: {s['total_duration_min']:.0f} min")
        print("="*50 + "\n")
    
    # =========================================================================
    # Database Methods
    # =========================================================================
    
    def _init_database(self) -> None:
        """Initialize database connection and repositories."""
        try:
            from db.connection import Database
            from db.repositories import (
                ZoneRepository, EmployeeRepository, ClusterRepository,
                RouteRepository, VehicleRepository
            )
            
            self.db = Database()
            if self.db.test_connection():
                print("[DB] Connected to database")
                self.zone_repo = ZoneRepository(self.db)
                self.employee_repo = EmployeeRepository(self.db)
                self.cluster_repo = ClusterRepository(self.db)
                self.route_repo = RouteRepository(self.db)
                self.vehicle_repo = VehicleRepository(self.db)
            else:
                print("[DB] Connection failed, running without database")
                self.use_database = False
        except Exception as e:
            print(f"[DB] Error initializing database: {e}")
            self.use_database = False
    
    def clear_database(self):
        """Clear route-related database tables (preserves employees)."""
        if not self.use_database:
            return
        
        print("[DB] Clearing route data (preserving employees)...")
        try:
            # Clear route-related tables but keep employees
            self.db.execute("""
                TRUNCATE TABLE 
                    employee_stop_assignments,
                    route_modifications,
                    route_stops,
                    vehicle_assignments,
                    routes,
                    vehicles,
                    clusters,
                    zones
                CASCADE
            """)
            # Reset employee pickup points and cluster assignments
            self.db.execute("""
                UPDATE employees SET 
                    pickup_point = NULL,
                    cluster_id = NULL,
                    zone_id = NULL
                WHERE deleted_at IS NULL
            """)
            print("    ✓ Route data cleared, employees preserved")
        except Exception as e:
            print(f"    ✗ Error clearing tables: {e}")
    
    def save_to_db(self) -> dict:
        """Save all data to database. Returns counts of saved records."""
        if not self.use_database:
            print("[DB] Database not enabled, skipping save")
            return {}
        
        # Clear existing data first if configured
        if getattr(self.config, 'TRUNCATE_DATABASE_ON_SAVE', False):
            self.clear_database()
        
        print("[DB] Saving to database...")
        counts = {}
        
        try:
            # Save zones first (employees reference zones)
            zone_id_mapping = {}  # Map old index to new DB id
            if self.zone_service:
                zones = self.zone_service.get_zones()
                if zones:
                    for idx, zone_polygon in enumerate(zones):
                        # zones is a list of Shapely polygons
                        boundary_wkt = zone_polygon.wkt if hasattr(zone_polygon, 'wkt') else None
                        db_zone_id = self.zone_repo.save(f"Zone {idx}", boundary_wkt)
                        zone_id_mapping[idx] = db_zone_id
                    
                    # Update employee zone_ids to match DB IDs
                    for emp in self.employees:
                        if emp.zone_id is not None and emp.zone_id in zone_id_mapping:
                            emp.zone_id = zone_id_mapping[emp.zone_id]
                    
                    # Update cluster zone_ids to match DB IDs
                    for cluster in self.clusters:
                        if cluster.zone_id is not None and cluster.zone_id in zone_id_mapping:
                            cluster.zone_id = zone_id_mapping[cluster.zone_id]
                    
                    counts['zones'] = len(zones)
                    print(f"    ✓ Saved {counts['zones']} zones")
            
            # Clear zone_id from employees and clusters if zones weren't saved (to avoid FK violation)
            if 'zones' not in counts:
                for emp in self.employees:
                    emp.zone_id = None
                for cluster in self.clusters:
                    cluster.zone_id = None
            
            # Save clusters before employees (employees reference clusters)
            cluster_id_mapping = {}  # Map old cluster.id to new DB id
            if self.clusters:
                for cluster in self.clusters:
                    old_cluster_id = cluster.id
                    # Temporarily remove employees to save cluster first
                    temp_employees = cluster.employees
                    cluster.employees = []
                    db_cluster_id = self.cluster_repo.save(cluster)
                    cluster.employees = temp_employees
                    cluster_id_mapping[old_cluster_id] = db_cluster_id
                    cluster.id = db_cluster_id  # Update cluster's own ID
                    
                    # Update employee cluster_ids
                    for emp in cluster.employees:
                        emp.cluster_id = db_cluster_id
                
                counts['clusters'] = len(self.clusters)
                print(f"    ✓ Saved {counts['clusters']} clusters")
            
            # Save employees (now clusters exist for FK)
            # Save ALL employees including excluded ones
            employees_to_save = self.all_employees if self.all_employees else self.employees
            if employees_to_save:
                self.employee_repo.save_batch(employees_to_save)
                counts['employees'] = len(employees_to_save)
                print(f"    ✓ Saved {counts['employees']} employees")
            
            # Save vehicles before routes (routes reference vehicles)
            vehicle_id_mapping = {}
            if self.vehicles:
                for vehicle in self.vehicles:
                    old_vehicle_id = vehicle.id
                    db_vehicle_id = self.vehicle_repo.save(vehicle)
                    vehicle_id_mapping[old_vehicle_id] = db_vehicle_id
                    vehicle.id = db_vehicle_id
                counts['vehicles'] = len(self.vehicles)
                print(f"    ✓ Saved {counts['vehicles']} vehicles")
            
            # Save routes (clusters and vehicles already saved with updated IDs)
            route_count = 0
            for cluster in self.clusters:
                if cluster.route:
                    # Get updated vehicle_id from mapping
                    vehicle_id = None
                    if cluster.vehicle and cluster.vehicle.id in vehicle_id_mapping:
                        vehicle_id = vehicle_id_mapping[cluster.vehicle.id]
                    elif cluster.vehicle:
                        vehicle_id = cluster.vehicle.id
                    self.route_repo.save(cluster.route, cluster.id, vehicle_id)
                    route_count += 1
            counts['routes'] = route_count
            if route_count > 0:
                print(f"    ✓ Saved {counts['routes']} routes")
            
            print("[DB] Save complete")
            
        except Exception as e:
            print(f"[DB] Error saving to database: {e}")
            raise
        
        return counts
    
    def load_from_db(self) -> dict:
        """Load data from database. Returns counts of loaded records."""
        if not self.use_database:
            print("[DB] Database not enabled, skipping load")
            return {}
        
        print("[DB] Loading from database...")
        counts = {}
        
        try:
            # Load employees
            self.employees = self.employee_repo.find_all()
            counts['employees'] = len(self.employees)
            
            # Load clusters with employees
            self.clusters = self.cluster_repo.find_all(include_employees=True)
            counts['clusters'] = len(self.clusters)
            
            # Load routes for each cluster
            for cluster in self.clusters:
                route = self.route_repo.find_by_cluster(cluster.id)
                if route:
                    cluster.assign_route(route)
            
            # Load vehicles
            self.vehicles = self.vehicle_repo.find_all()
            counts['vehicles'] = len(self.vehicles)
            
            print(f"    ✓ Loaded {counts['employees']} employees, {counts['clusters']} clusters, {counts['vehicles']} vehicles")
            
        except Exception as e:
            print(f"[DB] Error loading from database: {e}")
        
        return counts
    
    def clear_db(self) -> None:
        """Clear all data from database (soft delete)."""
        if not self.use_database:
            return
        
        print("[DB] Clearing database...")
        self.route_repo.delete_all()
        self.cluster_repo.delete_all()
        self.employee_repo.delete_all()
        self.vehicle_repo.delete_all()
        print("[DB] Database cleared")
    
    def run(self, optimization_mode: str | None = None) -> None:
        # Apply optimization mode preset before running
        if hasattr(self.config, 'apply_optimization_mode'):
            self.config.apply_optimization_mode(optimization_mode)
        
        mode_label = getattr(self.config, 'OPTIMIZATION_MODE', 'balanced').upper()
        print("\n" + "="*50 + "\n        SERVICE ROUTE OPTIMIZATION\n" + "="*50)
        print(f"   Config: {self.config.NUM_EMPLOYEES} employees, {self.config.NUM_CLUSTERS} clusters")
        print(f"   Mode: {mode_label}  (walk ≤{self.config.MAX_WALK_DISTANCE}m, "
              f"cluster ≤{self.config.EMPLOYEES_PER_CLUSTER} emp, "
              f"vehicle ≤{self.config.VEHICLE_CAPACITY})")
        if self.use_database:
            print("   Database: ENABLED")
        print("="*50 + "\n")
        
        print("[0] Loading Safe Pickup Points...")
        self.safe_stops = self.location_service.get_transit_stops()
        print(f"    OK: {len(self.safe_stops)} stops loaded")
        
        self.generate_employees()
        self.create_zones()
        self.create_clusters()
        self.generate_stops()
        self.optimize_routes(use_stops=True)
        self.reassign_employees_to_closer_routes()  # Cross-cluster optimization
        self.assign_vehicles()
        # self.generate_maps()  # Disabled - maps now shown in web UI
        self.print_summary()
        
        # Save to database if enabled
        if self.use_database:
            self.save_to_db()

