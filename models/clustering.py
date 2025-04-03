import numpy as np
from sklearn.cluster import KMeans
import math
from collections import defaultdict

def cluster_locations(locations, num_clusters):
    """
    Enhanced clustering of delivery locations for multiple vehicles.
    
    Args:
        locations (list): List of locations with latitude and longitude
        num_clusters (int): Number of clusters to create (typically number of vehicles)
        
    Returns:
        list: List of lists containing location indices for each cluster
    """
    # Extract depot for separate handling
    depot = locations[0]  # First location is assumed to be the depot
    delivery_locations = locations[1:]  # Rest are delivery locations
    
    # Check if we have enough points to cluster
    if len(delivery_locations) < num_clusters:
        # Not enough points, assign one location per vehicle
        # and remaining vehicles get empty routes
        clusters = []
        for i in range(min(num_clusters, len(delivery_locations))):
            clusters.append([i+1])  # +1 to account for depot at index 0
        
        # Fill remaining clusters with empty lists
        while len(clusters) < num_clusters:
            clusters.append([])
            
        return clusters
    
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
    
    # Check for time windows to incorporate into clustering
    has_time_windows = any(loc.get('time_window_start') for loc in delivery_locations)
    
    if has_time_windows:
        # If we have time windows, add time as a third dimension for clustering
        time_values = []
        for loc in delivery_locations:
            if loc.get('time_window_start'):
                # Use middle of time window
                start_time = _parse_time(loc['time_window_start'])
                end_time = _parse_time(loc['time_window_end'])
                middle_time = (start_time + end_time) / 2
                time_values.append(middle_time)
            else:
                # Use noon as default
                time_values.append(12.0)
        
        # Scale time to have similar influence (0-24 hours -> 0-20 km equivalent)
        time_scale = 0.8  # Controls influence of time vs. distance
        scaled_time = np.array(time_values) * time_scale
        
        # Add time dimension to coordinates
        time_coords = np.column_stack((normalized_coords, scaled_time))
        clustering_data = time_coords
    else:
        clustering_data = normalized_coords
    
    # Apply K-means clustering with multiple initializations for better results
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(clustering_data)
    
    # Reorganize locations into clusters
    clusters = defaultdict(list)
    for i, label in enumerate(cluster_labels):
        # Add 1 to index to account for depot being at index 0
        clusters[label].append(i + 1)
    
    # Make sure all clusters have at least one stop
    empty_clusters = []
    for i in range(num_clusters):
        if i not in clusters:
            empty_clusters.append(i)
    
    # Redistribute from largest clusters if some are empty
    if empty_clusters:
        for empty_cluster in empty_clusters:
            # Find the largest cluster
            largest_cluster = max(clusters.items(), key=lambda x: len(x[1]))
            largest_cluster_id = largest_cluster[0]
            
            if len(clusters[largest_cluster_id]) > 1:
                # Take a location from the largest cluster
                location = clusters[largest_cluster_id].pop()
                clusters[empty_cluster] = [location]
    
    # Convert to list of lists format
    cluster_lists = []
    for i in range(num_clusters):
        cluster_lists.append(clusters.get(i, []))
    
    return cluster_lists

def _parse_time(time_str):
    """Helper function to parse time string to hours (float)"""
    if not time_str:
        return 12.0  # Default to noon
    
    try:
        # Handle "HH:MM" format
        if ':' in time_str:
            hours, minutes = map(int, time_str.split(':'))
            return hours + minutes / 60.0
        # Handle numeric format
        elif len(time_str) <= 2:
            return float(time_str)
        else:
            # Assume format like "1100" for 11:00
            hours = int(time_str[:-2])
            minutes = int(time_str[-2:])
            return hours + minutes / 60.0
    except:
        # Return noon as default if parsing fails
        return 12.0

def balance_clusters(clusters, locations, distance_matrix):
    """
    Improve cluster balance to ensure even workload distribution.
    
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
        
        # If cluster is empty, distance is 0
        if not cluster:
            cluster_distances.append(0)
            continue
        
        # Calculate distance within the cluster, following order
        for loc_idx in cluster:
            total_dist += distance_matrix[prev_idx][loc_idx]
            prev_idx = loc_idx
        
        # Return to depot
        total_dist += distance_matrix[prev_idx][depot_idx]
        cluster_distances.append(total_dist)
    
    # Check if we need to balance
    if not cluster_distances or max(cluster_distances) == 0:
        return clusters
    
    # If clusters are already balanced, return them as-is
    if max(cluster_distances) - min(cluster_distances) < 0.2 * np.mean(cluster_distances):
        return clusters
    
    # Get largest and smallest clusters by distance
    max_cluster_idx = np.argmax(cluster_distances)
    min_cluster_idx = np.argmin(cluster_distances)
    
    # Skip balancing if either cluster is empty
    if len(clusters[max_cluster_idx]) <= 1 or not clusters[min_cluster_idx]:
        return clusters
    
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