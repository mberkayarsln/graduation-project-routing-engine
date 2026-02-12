"""Repository for Cluster entity."""
from __future__ import annotations

from db.connection import Database
from db.repositories.base_repository import BaseRepository
from db.repositories.employee_repository import EmployeeRepository
from models import Cluster, Employee


class ClusterRepository(BaseRepository[Cluster]):
    """Repository for managing clusters in the database."""
    
    def __init__(self, db: Database | None = None) -> None:
        super().__init__(db)
        self.employee_repo = EmployeeRepository(self.db)
    
    @property
    def table_name(self) -> str:
        return "clusters"
    
    def to_model(self, row: dict, employees: list[Employee] | None = None) -> Cluster:
        """Convert database row to Cluster object."""
        center = self.point_from_row(row, "center_location_wkt")
        if not center:
            center = (0.0, 0.0)
        
        cluster = Cluster(id=row["id"], center=center)
        cluster.zone_id = row.get("zone_id")
        
        # Parse original_center if exists
        original = self.point_from_row(row, "original_center_wkt")
        if original:
            cluster.original_center = original
        
        # Add employees if provided
        if employees:
            for emp in employees:
                cluster.employees.append(emp)
                emp.cluster_id = cluster.id
        
        return cluster
    
    def find_all(self, limit: int = 1000, include_employees: bool = False) -> list[Cluster]:
        """Find all active clusters."""
        query = """
            SELECT id, zone_id,
                   ST_AsText(center_location) as center_location_wkt,
                   ST_AsText(original_center) as original_center_wkt
            FROM clusters
            WHERE deleted_at IS NULL
            ORDER BY id
            LIMIT %s
        """
        rows = self.db.fetchall(query, (limit,))
        clusters = []
        for row in rows:
            employees = None
            if include_employees:
                employees = self.employee_repo.find_by_cluster(row["id"])
            clusters.append(self.to_model(row, employees))
        return clusters
    
    def find_by_id(self, id: int, include_employees: bool = True) -> Cluster | None:
        """Find cluster by ID with optional employees."""
        query = """
            SELECT id, zone_id,
                   ST_AsText(center_location) as center_location_wkt,
                   ST_AsText(original_center) as original_center_wkt
            FROM clusters
            WHERE id = %s AND deleted_at IS NULL
        """
        row = self.db.fetchone(query, (id,))
        if not row:
            return None
        
        employees = None
        if include_employees:
            employees = self.employee_repo.find_by_cluster(id)
        return self.to_model(row, employees)
    


    
    def save(self, cluster: Cluster) -> int:
        """Insert or update a cluster. Returns the ID."""
        center_wkt = self.point_to_wkt(cluster.center[0], cluster.center[1])
        original_wkt = None
        if cluster.original_center:
            original_wkt = self.point_to_wkt(cluster.original_center[0], cluster.original_center[1])
        
        # Check if cluster exists
        existing = self.db.fetchone(
            "SELECT id FROM clusters WHERE id = %s AND deleted_at IS NULL",
            (cluster.id,)
        )
        
        if existing:
            # Update
            query = """
                UPDATE clusters SET
                    zone_id = %s,
                    center_location = ST_GeomFromText(%s, 4326),
                    original_center = CASE WHEN %s IS NOT NULL THEN ST_GeomFromText(%s, 4326) ELSE original_center END,
                    updated_at = now()
                WHERE id = %s
            """
            self.db.execute(query, (
                cluster.zone_id, center_wkt,
                original_wkt, original_wkt,
                cluster.id
            ))
            cluster_id = cluster.id
        else:
            # Insert
            query = """
                INSERT INTO clusters (zone_id, center_location, original_center)
                VALUES (%s, ST_GeomFromText(%s, 4326), 
                        CASE WHEN %s IS NOT NULL THEN ST_GeomFromText(%s, 4326) ELSE NULL END)
                RETURNING id
            """
            cluster_id = self.db.fetchval(query, (
                cluster.zone_id, center_wkt,
                original_wkt, original_wkt
            ))
            cluster.id = cluster_id
        
        # Update employee cluster assignments
        for emp in cluster.employees:
            emp.cluster_id = cluster_id
            self.employee_repo.update_cluster_assignment(emp.id, cluster_id)
        
        return cluster_id
    
    def save_batch(self, clusters: list[Cluster]) -> list[int]:
        """Bulk save clusters. Returns list of IDs."""
        ids = []
        for cluster in clusters:
            ids.append(self.save(cluster))
        return ids
    
    def delete_all(self) -> int:
        """Soft delete all clusters and clear employee assignments."""
        self.employee_repo.clear_all_clusters()
        query = "UPDATE clusters SET deleted_at = now() WHERE deleted_at IS NULL"
        self.db.execute(query)
        return 0
