import numpy as np
from sklearn.cluster import KMeans
import math
from collections import defaultdict

def cluster_locations(locations, num_clusters):
    """
    Cluster delivery locations using K-means.
    
    Args:
        locations (list): List of locations with latitude and longitude
        num_clusters (int): Number of clusters to create
        
    Returns:
        list: List of lists containing location indices for each cluster
    """
    # Extract coordinates for clustering
    depot = locations[0]  # First location is assumed to be the depot
    delivery_locations = locations[1:]  # Rest are delivery locations
    
    # Check if we have enough points to cluster
    if len(delivery_locations) < num_clusters:
        # Not enough points, create one cluster with all points
        return [list(range(1, len(locations)))]
    
    # Prepare data for K-means clustering
    coordinates = np.array([[loc['latitude'], loc['longitude']] for loc in delivery_locations])
    
    # Normalize coordinates to account for latitude/longitude distortion
    # Approximate conversion: 1 degree latitude ≈ 111 km, 1 degree longitude varies with latitude
    avg_lat = np.mean(coordinates[:, 0])
    lat_scale = 111.0
    lng_scale = 111.0 * math.cos(math.radians(avg_lat))
    
    normalized_coords = np.zeros_like(coordinates)
    normalized_coords[:, 0] = coordinates[:, 0] * lat_scale
    normalized_coords[:, 1] = coordinates[:, 1] * lng_scale
    
    # Apply K-means clustering
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(normalized_coords)
    
    # Reorganize locations into clusters
    clusters = defaultdict(list)
    for i, label in enumerate(cluster_labels):
        # Add 1 to index to account for depot being at index 0
        clusters[label].append(i + 1)
    
    # Return clusters as list of lists
    return [clusters[i] for i in range(num_clusters)]

def balance_clusters(clusters, locations, distance_matrix):
    """
    Balance clusters to ensure even workload distribution.
    
    Args:
        clusters (list): List of clusters (each cluster is a list of location indices)
        locations (list): List of all locations
        distance_matrix (list): Distance matrix between all locations
        
    Returns:
        list: Balanced clusters
    """
    depot_idx = 0  # Assuming depot is at index 0
    
    # Calculate total distance for each cluster
    cluster_distances = []
    for cluster in clusters:
        total_dist = 0
        prev_idx = depot_idx
        
        # Calculate distance within the cluster, following order
        for loc_idx in cluster:
            total_dist += distance_matrix[prev_idx][loc_idx]
            prev_idx = loc_idx
        
        # Return to depot
        total_dist += distance_matrix[prev_idx][depot_idx]
        cluster_distances.append(total_dist)
    
    # If clusters are already balanced, return them as-is
    if max(cluster_distances) - min(cluster_distances) < 0.2 * np.mean(cluster_distances):
        return clusters
    
    # Get largest and smallest clusters by distance
    max_cluster_idx = np.argmax(cluster_distances)
    min_cluster_idx = np.argmin(cluster_distances)
    
    # Find the best point to move from largest to smallest cluster
    best_point = None
    best_improvement = 0
    
    for point_idx in clusters[max_cluster_idx]:
        # Calculate improvement if we move this point
        # First, calculate distance reduction in the source cluster
        source_reduction = 0
        for other_idx in clusters[max_cluster_idx]:
            if other_idx != point_idx:
                source_reduction += distance_matrix[point_idx][other_idx]
        
        # Calculate distance increase in the target cluster
        target_increase = 0
        for other_idx in clusters[min_cluster_idx]:
            target_increase += distance_matrix[point_idx][other_idx]
        
        # Overall improvement
        improvement = source_reduction - target_increase
        
        if improvement > best_improvement:
            best_improvement = improvement
            best_point = point_idx
    
    # If we found a good point to move, update clusters
    if best_point is not None:
        clusters[max_cluster_idx].remove(best_point)
        clusters[min_cluster_idx].append(best_point)
        
        # Recursively balance again
        return balance_clusters(clusters, locations, distance_matrix)
    
    return clusters