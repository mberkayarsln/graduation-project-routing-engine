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
    
    def find_optimal_clusters(self, employees, max_clusters=15):
        """Find optimal number of clusters using elbow method."""
        coordinates = np.array([[emp.lat, emp.lon] for emp in employees])
        
        inertias = []
        for k in range(1, min(max_clusters + 1, len(employees))):
            clusterer = KMeansClusterer(n_clusters=k, random_state=42)
            clusterer.fit(coordinates)
            inertias.append(clusterer.inertia_)
        
        # TODO: Implement elbow detection
        return self.config.NUM_CLUSTERS
    
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
    
    def get_clustering_stats(self):
        """Return clustering statistics."""
        if self.clusterer is None:
            return None
        
        return self.clusterer.get_stats()
    
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
