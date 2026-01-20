"""Clustering Service - handles employee clustering operations."""
import numpy as np
from core.cluster import Cluster
from utils.kmeans import KMeansClusterer


class ClusteringService:
    """Service for clustering employees into groups."""
    
    def __init__(self, config):
        self.config = config
        self.algorithm = 'kmeans'
        self.clusterer = None
    
    def cluster_employees(self, employees, num_clusters, random_state=None):
        """
        Cluster employees into groups.
        
        Args:
            employees: List of Employee objects
            num_clusters: Number of clusters to create
            random_state: Random seed for reproducibility
        
        Returns:
            List of Cluster objects with employees assigned
        """
        if self.algorithm == 'kmeans':
            return self._cluster_kmeans(employees, num_clusters, random_state)
        else:
            raise ValueError(f"Unsupported algorithm: {self.algorithm}")
    
    def _cluster_kmeans(self, employees, num_clusters, random_state):
        """Perform KMeans clustering."""
        self.clusterer = KMeansClusterer(
            n_clusters=num_clusters,
            random_state=random_state
        )
        coordinates = np.array([[emp.lat, emp.lon] for emp in employees])
        
        self.clusterer.fit(coordinates)
        
        # Create cluster objects
        clusters = []
        for i in range(num_clusters):
            center = tuple(self.clusterer.cluster_centers_[i])
            cluster = Cluster(id=i, center=center)
            clusters.append(cluster)
        
        # Assign employees to clusters
        for employee, cluster_id in zip(employees, self.clusterer.labels_):
            clusters[cluster_id].add_employee(employee)
        
        return clusters
    
    
    def cluster_by_zones(self, zone_assignments, employees_per_cluster=20, random_state=None):
        """
        Cluster employees within each zone separately.
        
        Args:
            zone_assignments: Dict mapping zone_id -> list of employees
            employees_per_cluster: Target number of employees per cluster
            random_state: Random seed for reproducibility
            
        Returns:
            List of Cluster objects with employees assigned
        """
        clusters = []
        global_cluster_id = 0
        
        for zone_id, zone_employees in zone_assignments.items():
            if not zone_employees:
                continue
            
            n_employees = len(zone_employees)
            
            # Calculate clusters needed (ceiling division to enforce max size)
            # e.g., 35 employees with max 17 → ceil(35/17) = 3 clusters (not 2)
            import math
            n_clusters_zone = max(1, math.ceil(n_employees / employees_per_cluster))
            
            # Don't create more clusters than employees
            n_clusters_zone = min(n_clusters_zone, n_employees)
            
            print(f"   Zone {zone_id}: {n_employees} employees → {n_clusters_zone} cluster(s)")
            
            if n_clusters_zone == 1:
                # Single cluster for small zones
                coords = [[e.lat, e.lon] for e in zone_employees]
                center = (
                    sum(c[0] for c in coords) / len(coords),
                    sum(c[1] for c in coords) / len(coords)
                )
                cluster = Cluster(id=global_cluster_id, center=center)
                cluster.zone_id = zone_id
                
                for emp in zone_employees:
                    cluster.add_employee(emp)
                
                clusters.append(cluster)
                global_cluster_id += 1
            else:
                # KMeans clustering within zone
                zone_clusterer = KMeansClusterer(
                    n_clusters=n_clusters_zone,
                    random_state=random_state
                )
                coordinates = np.array([[emp.lat, emp.lon] for emp in zone_employees])
                zone_clusterer.fit(coordinates)
                
                # Create cluster objects for this zone
                zone_clusters = []
                for i in range(n_clusters_zone):
                    center = tuple(zone_clusterer.cluster_centers_[i])
                    cluster = Cluster(id=global_cluster_id, center=center)
                    cluster.zone_id = zone_id
                    zone_clusters.append(cluster)
                    global_cluster_id += 1
                
                # Assign employees to clusters
                for employee, cluster_idx in zip(zone_employees, zone_clusterer.labels_):
                    zone_clusters[cluster_idx].add_employee(employee)
                
                clusters.extend(zone_clusters)
        
        return clusters
    
    
    def snap_centers_to_roads(self, clusters):
        """
        Snap cluster centers to the nearest roads using OSRM.
        
        Args:
            clusters: List of Cluster objects
            
        Returns:
            Number of centers successfully snapped
        """
        from routing_engines.osrm import OSRMRouter
        router = OSRMRouter()
        
        snapped_count = 0
        for cluster in clusters:
            original_center = cluster.center
            result = router.snap_to_road(original_center[0], original_center[1])
            
            if result:
                new_center = (result['lat'], result['lon'])
                cluster.center = new_center
                cluster.original_center = original_center  # Store original for reference
                snapped_count += 1
                
                if result['name']:
                    print(f"   Cluster {cluster.id}: snapped to '{result['name']}' "
                          f"({result['distance']:.0f}m from centroid)")
                else:
                    print(f"   Cluster {cluster.id}: snapped to road "
                          f"({result['distance']:.0f}m from centroid)")
            else:
                print(f"   Cluster {cluster.id}: could not snap (keeping centroid)")
        
        return snapped_count
    
    def enforce_capacity_constraints(self, clusters, vehicle_capacity):
        """
        Split clusters that exceed vehicle capacity.
        
        Args:
            clusters: List of Cluster objects
            vehicle_capacity: Maximum employees per vehicle
            
        Returns:
            New list of clusters with capacity constraints enforced
        """
        import math
        
        new_clusters = []
        next_id = max(c.id for c in clusters) + 1
        splits_count = 0
        
        for cluster in clusters:
            active_count = cluster.get_employee_count(include_excluded=False)
            
            if active_count <= vehicle_capacity:
                # Cluster is within capacity
                new_clusters.append(cluster)
            else:
                # Need to split this cluster
                n_splits = math.ceil(active_count / vehicle_capacity)
                splits_count += 1
                
                print(f"   Cluster {cluster.id}: {active_count} employees exceeds capacity {vehicle_capacity}, "
                      f"splitting into {n_splits} sub-clusters")
                
                active_employees = cluster.get_active_employees()
                
                if n_splits >= len(active_employees):
                    # Edge case: more splits than employees, just use one per cluster
                    for emp in active_employees:
                        sub_cluster = Cluster(id=next_id, center=(emp.lat, emp.lon))
                        sub_cluster.zone_id = getattr(cluster, 'zone_id', None)
                        sub_cluster.add_employee(emp)
                        new_clusters.append(sub_cluster)
                        next_id += 1
                else:
                    # Sub-cluster using KMeans
                    sub_clusterer = KMeansClusterer(
                        n_clusters=n_splits,
                        random_state=42
                    )
                    coordinates = np.array([[emp.lat, emp.lon] for emp in active_employees])
                    sub_clusterer.fit(coordinates)
                    
                    # Create sub-clusters
                    sub_clusters = []
                    for i in range(n_splits):
                        center = tuple(sub_clusterer.cluster_centers_[i])
                        sub_cluster = Cluster(id=next_id, center=center)
                        sub_cluster.zone_id = getattr(cluster, 'zone_id', None)
                        sub_cluster.parent_cluster_id = cluster.id
                        sub_clusters.append(sub_cluster)
                        next_id += 1
                    
                    # Assign employees to sub-clusters
                    for emp, label in zip(active_employees, sub_clusterer.labels_):
                        sub_clusters[label].add_employee(emp)
                    
                    # Also add excluded employees to the nearest sub-cluster
                    excluded_employees = [e for e in cluster.employees if e.excluded]
                    for emp in excluded_employees:
                        # Find nearest sub-cluster center
                        min_dist = float('inf')
                        nearest_sub = sub_clusters[0]
                        for sc in sub_clusters:
                            dist = emp.distance_to(sc.center[0], sc.center[1])
                            if dist < min_dist:
                                min_dist = dist
                                nearest_sub = sc
                        nearest_sub.add_employee(emp)
                    
                    new_clusters.extend(sub_clusters)
                    
                    for sc in sub_clusters:
                        print(f"      → Sub-cluster {sc.id}: {sc.get_employee_count(include_excluded=False)} employees")
        
        if splits_count > 0:
            print(f"   Capacity enforcement: {splits_count} clusters split, "
                  f"{len(new_clusters)} total clusters")
        
        return new_clusters
    
    def validate_capacity(self, clusters, vehicle_capacity):
        """
        Validate that all clusters are within vehicle capacity.
        
        Args:
            clusters: List of Cluster objects
            vehicle_capacity: Maximum employees per vehicle
            
        Returns:
            Tuple of (is_valid, list of violations)
        """
        violations = []
        
        for cluster in clusters:
            active_count = cluster.get_employee_count(include_excluded=False)
            if active_count > vehicle_capacity:
                violations.append({
                    'cluster_id': cluster.id,
                    'employee_count': active_count,
                    'capacity': vehicle_capacity,
                    'excess': active_count - vehicle_capacity
                })
        
        return len(violations) == 0, violations
