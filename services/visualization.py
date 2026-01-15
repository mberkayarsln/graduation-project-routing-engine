"""Visualization Service - generates HTML maps for routes and clusters."""
import folium


class VisualizationService:
    """Service for creating Folium map visualizations."""
    
    def __init__(self, config):
        self.config = config
        self.office_location = config.OFFICE_LOCATION
        self.cluster_colors = {}
    
    def _get_cluster_color(self, cluster_id):
        """Generate a unique color for a cluster."""
        if cluster_id not in self.cluster_colors:
            import random
            import hashlib
            
            seed_str = f"cluster_{cluster_id}_color_seed"
            hash_value = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
            random.seed(hash_value)
            
            golden_ratio = 0.618033988749895
            hue = int((cluster_id * golden_ratio * 360) % 360)
            hue = (hue + random.randint(-30, 30)) % 360
            saturation = random.randint(65, 95)
            lightness = random.randint(40, 70)
            
            self.cluster_colors[cluster_id] = f'hsl({hue}, {saturation}%, {lightness}%)'
        return self.cluster_colors[cluster_id]
    
    def create_employees_map(self, employees):
        """Create a map showing all employee locations."""
        filename = "maps/employees.html"
        
        if not employees:
            return filename
        
        avg_lat = sum(emp.lat for emp in employees) / len(employees)
        avg_lon = sum(emp.lon for emp in employees) / len(employees)
        
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
        
        folium.Marker(
            location=self.office_location,
            popup="<b>Office</b>",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        for emp in employees:
            folium.CircleMarker(
                location=[emp.lat, emp.lon],
                radius=4,
                color='#2563eb',
                fill=True,
                fill_opacity=0.7,
                popup=f"<b>ID:</b> {emp.id}"
            ).add_to(m)
        
        m.save(filename)
        return filename
    
    def create_clusters_map(self, clusters):
        """Create a map showing clusters with their employees."""
        filename = "maps/clusters.html"
        
        all_employees = []
        for cluster in clusters:
            all_employees.extend(cluster.employees)
        
        if not all_employees:
            return filename
        
        avg_lat = sum(emp.lat for emp in all_employees) / len(all_employees)
        avg_lon = sum(emp.lon for emp in all_employees) / len(all_employees)
        
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
        
        folium.Marker(
            location=self.office_location,
            popup="<b>Office</b>",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Add cluster centers
        for cluster in clusters:
            folium.Marker(
                location=cluster.center,
                popup=f"<b>Cluster {cluster.id}</b><br>Center",
                icon=folium.Icon(color='black', icon='star', prefix='fa')
            ).add_to(m)
        
        # Add employees colored by cluster
        for emp in all_employees:
            cluster_id = emp.cluster_id
            color = self._get_cluster_color(cluster_id)
            
            folium.CircleMarker(
                location=[emp.lat, emp.lon],
                radius=5,
                color=color,
                fill=True,
                fill_opacity=0.7,
                popup=f"<b>ID:</b> {emp.id}<br><b>Cluster:</b> {cluster_id}"
            ).add_to(m)
        
        m.save(filename)
        return filename
    
    def create_routes_map(self, clusters):
        """Create a map showing optimized routes for all clusters."""
        filename = "maps/optimized_routes.html"
        
        routes_dict = {}
        for cluster in clusters:
            if cluster.route:
                routes_dict[cluster.id] = cluster.route
        
        if not routes_dict:
            return filename
        
        m = folium.Map(location=self.office_location, zoom_start=11)
        
        folium.Marker(
            location=self.office_location,
            popup="<b>Office</b>",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        for cluster_id, route in routes_dict.items():
            cluster = clusters[int(cluster_id)]
            color = self._get_cluster_color(int(cluster_id))
            
            # Draw route polyline
            if route.coordinates:
                folium.PolyLine(
                    route.coordinates,
                    color=color,
                    weight=4,
                    opacity=0.7,
                    popup=f"<b>Vehicle Route - Cluster {cluster_id}</b>"
                ).add_to(m)
            
            # Draw employees
            if cluster.has_stops():
                for employee in cluster.get_active_employees():
                    stop_index, stop_location = cluster.get_employee_stop(employee)
                    target_location = employee.pickup_point if hasattr(employee, 'pickup_point') and employee.pickup_point else stop_location
                    
                    if target_location:
                        folium.CircleMarker(
                            location=employee.get_location(),
                            radius=3,
                            color=color,
                            fill=True,
                            fill_opacity=0.5,
                            popup=f"<b>ID:</b> {employee.id}"
                        ).add_to(m)
            else:
                for i, stop in enumerate(route.stops):
                    folium.CircleMarker(
                        location=stop,
                        radius=6,
                        color=color,
                        fill=True,
                        fill_opacity=0.9,
                        popup=f"<b>Cluster {cluster_id}</b><br>Point {i}"
                    ).add_to(m)
            
            # Add cluster center marker
            center = cluster.center
            n_stops = len(cluster.stops) if cluster.has_stops() else len(route.stops)
            
            folium.Marker(
                location=center,
                popup=f"<b>Cluster {cluster_id}</b><br>"
                      f"{n_stops} stops<br>"
                      f"{route.distance_km:.1f} km<br>"
                      f"{route.duration_min:.0f} min",
                icon=folium.DivIcon(html=f"""
                    <div style="background: {color}; color: white; 
                         padding: 5px; border-radius: 50%; 
                         width: 30px; height: 30px; text-align: center;
                         line-height: 30px; font-weight: bold;
                         border: 3px solid white;
                         box-shadow: 0 3px 6px rgba(0,0,0,0.4);">
                        {cluster_id}
                    </div>
                """)
            ).add_to(m)
        
        m.save(filename)
        return filename
    
    def create_cluster_detail_map(self, cluster):
        """Create a detailed map for a single cluster."""
        import os
        os.makedirs("maps/detailed", exist_ok=True)
        
        filename = f"maps/detailed/cluster_{cluster.id}_detail.html"
        m = folium.Map(location=cluster.center, zoom_start=14)
        
        color = self._get_cluster_color(cluster.id)
        
        # Office marker
        folium.Marker(
            location=self.office_location,
            popup="<b>Office</b>",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Cluster center
        folium.Marker(
            location=cluster.center,
            popup=f"<b>Cluster {cluster.id} Center</b>",
            icon=folium.Icon(color='black', icon='star', prefix='fa')
        ).add_to(m)
        
        # Employees with pickup lines
        for employee in cluster.employees:
            if employee.excluded:
                folium.CircleMarker(
                    location=employee.get_location(),
                    radius=4,
                    color='gray',
                    fill=True,
                    fillColor='lightgray',
                    fillOpacity=0.5,
                    popup=f"<b>ID:</b> {employee.id}<br>"
                          f"<b>Status:</b> Excluded<br>"
                          f"<b>Reason:</b> {employee.exclusion_reason}",
                    weight=1
                ).add_to(m)
            else:
                stop_index, stop_location = cluster.get_employee_stop(employee)
                target_location = employee.pickup_point if hasattr(employee, 'pickup_point') and employee.pickup_point else stop_location
                
                if target_location:
                    walk_distance = employee.distance_to(target_location[0], target_location[1])
                    
                    # Draw walking line
                    folium.PolyLine(
                        [employee.get_location(), target_location],
                        color=color,
                        weight=1.5,
                        opacity=0.6,
                        dash_array='5, 5',
                        popup=f"Pick-up: {employee.id}"
                    ).add_to(m)
                    
                    # Walking distance label
                    midpoint = [
                        (employee.lat + target_location[0]) / 2,
                        (employee.lon + target_location[1]) / 2
                    ]
                    
                    folium.Marker(
                        location=midpoint,
                        icon=folium.DivIcon(icon_size=(100, 20), icon_anchor=(50, 10), html=f"""
                            <div style="font-size: 10px; color: {color}; font-weight: bold; 
                                 background: rgba(255, 255, 255, 0.7); padding: 0 2px; border-radius: 3px;
                                 text-align: center; width: auto; display: inline-block;">
                                {walk_distance:.0f}m
                            </div>
                        """)
                    ).add_to(m)
                
                # Employee marker
                folium.CircleMarker(
                    location=employee.get_location(),
                    radius=5,
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.7,
                    popup=f"<b>ID:</b> {employee.id}<br>"
                          f"<b>Stop:</b> {stop_index+1 if stop_index is not None else 'N/A'}",
                    weight=2
                ).add_to(m)
                
                # Bus stop indicator
                is_safe_stop = hasattr(employee, 'pickup_type') and employee.pickup_type == 'stop'
                
                if is_safe_stop and target_location:
                    folium.Marker(
                        location=target_location,
                        icon=folium.DivIcon(
                            html='<div style="font-size: 20px; color: green; text-shadow: 1px 1px 2px white;"><i class="fa fa-bus"></i></div>',
                            icon_size=(20, 20),
                            icon_anchor=(10, 10)
                        ),
                        popup="Transit Stop (Safe Point)"
                    ).add_to(m)
        
        # Route polyline
        if cluster.route and cluster.route.coordinates:
            folium.PolyLine(
                cluster.route.coordinates,
                color=color,
                weight=5,
                opacity=0.8,
                popup=f"<b>Vehicle Route</b><br>"
                      f"{cluster.route.distance_km:.1f} km<br>"
                      f"{cluster.route.duration_min:.0f} min"
            ).add_to(m)
        
        m.save(filename)
        return filename
    
    def create_zones_map(self, clusters, zones=None, barrier_roads=None):
        """Create a map showing zone boundaries with clusters."""
        filename = "maps/zones.html"
        
        all_employees = []
        for cluster in clusters:
            all_employees.extend(cluster.employees)
        
        if not all_employees:
            return filename
        
        avg_lat = sum(emp.lat for emp in all_employees) / len(all_employees)
        avg_lon = sum(emp.lon for emp in all_employees) / len(all_employees)
        
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
        
        # Office marker
        folium.Marker(
            location=self.office_location,
            popup="<b>Office</b>",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Draw zone boundaries
        if zones:
            for zone_id, zone_polygon in enumerate(zones):
                try:
                    if hasattr(zone_polygon, 'exterior'):
                        coords = [[c[1], c[0]] for c in zone_polygon.exterior.coords]
                        folium.Polygon(
                            locations=coords,
                            color='#333333',
                            weight=2,
                            fill=True,
                            fill_opacity=0.1,
                            popup=f"<b>Zone {zone_id}</b>"
                        ).add_to(m)
                except Exception:
                    pass
        
        # Draw barrier roads
        if barrier_roads:
            try:
                from shapely.geometry import MultiLineString, LineString
                if isinstance(barrier_roads, MultiLineString):
                    for line in barrier_roads.geoms:
                        coords = [[c[1], c[0]] for c in line.coords]
                        folium.PolyLine(
                            locations=coords,
                            color='#dc2626',
                            weight=4,
                            opacity=0.8,
                            popup="Barrier Road"
                        ).add_to(m)
                elif isinstance(barrier_roads, LineString):
                    coords = [[c[1], c[0]] for c in barrier_roads.coords]
                    folium.PolyLine(
                        locations=coords,
                        color='#dc2626',
                        weight=4,
                        opacity=0.8,
                        popup="Barrier Road"
                    ).add_to(m)
            except Exception:
                pass
        
        # Draw employees colored by zone
        for emp in all_employees:
            zone_id = getattr(emp, 'zone_id', 0)
            color = self._get_cluster_color(zone_id * 10)  # Different color space for zones
            
            folium.CircleMarker(
                location=[emp.lat, emp.lon],
                radius=4,
                color=color,
                fill=True,
                fill_opacity=0.6,
                popup=f"<b>ID:</b> {emp.id}<br><b>Zone:</b> {zone_id}<br><b>Cluster:</b> {emp.cluster_id}"
            ).add_to(m)
        
        m.save(filename)
        return filename
    
    def create_all_maps(self, clusters, zones=None, barrier_roads=None):
        """Create all map visualizations."""
        import os
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        files = []
        all_employees = []
        for cluster in clusters:
            all_employees.extend(cluster.employees)
        
        files.append(self.create_employees_map(all_employees))
        files.append(self.create_clusters_map(clusters))
        files.append(self.create_routes_map(clusters))
        
        if zones or barrier_roads:
            files.append(self.create_zones_map(clusters, zones, barrier_roads))
        
        for cluster in clusters:
            detail_file = self.create_cluster_detail_map(cluster)
            files.append(detail_file)
        
        return files

