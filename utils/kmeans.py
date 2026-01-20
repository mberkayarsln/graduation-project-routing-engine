"""KMeans Clusterer - wrapper for scikit-learn KMeans."""
from sklearn.cluster import KMeans
import numpy as np


class KMeansClusterer:
    """KMeans clustering wrapper with convenience methods."""
    
    def __init__(self, n_clusters=5, random_state=42, n_init=10):
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.n_init = n_init
        self.model = None
        self.cluster_centers_ = None
        self.labels_ = None
        self.inertia_ = None
    
    def fit(self, coordinates):
        """
        Fit KMeans model to coordinates.
        
        Args:
            coordinates: Array of shape (n_samples, 2) with [lat, lon]
        
        Returns:
            self
        """
        self.model = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init=self.n_init
        )
        
        self.labels_ = self.model.fit_predict(coordinates)
        self.cluster_centers_ = self.model.cluster_centers_
        self.inertia_ = self.model.inertia_
        
        return self
