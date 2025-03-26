import requests
import json
import time
import numpy as np
import os
from math import radians, sin, cos, sqrt, atan2
import networkx as nx
from queue import PriorityQueue

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points
    on the Earth's surface given their latitude and longitude.
    
    Args:
        lat1, lon1: Coordinates of the first point
        lat2, lon2: Coordinates of the second point
        
    Returns:
        float: Distance in kilometers
    """
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    radius = 6371  # Earth's radius in kilometers
    
    return radius * c

def calculate_distance_matrix(coordinates, use_osrm=False, osrm_server=None):
    """
    Calculate a distance matrix between all points.
    """
    n = len(coordinates)
    distance_matrix = [[0 for _ in range(n)] for _ in range(n)]
    
    # Print debug information
    print(f"Calculating distances between {n} points")
    print(f"First coordinate: {coordinates[0] if coordinates else 'None'}")
    
    # Fall back to direct haversine distances
    for i in range(n):
        for j in range(n):
            if i == j:
                distance_matrix[i][j] = 0
            else:
                lat1 = coordinates[i]['lat']
                lng1 = coordinates[i]['lng']
                lat2 = coordinates[j]['lat']
                lng2 = coordinates[j]['lng']
                
                distance_matrix[i][j] = haversine_distance(lat1, lng1, lat2, lng2)
    
    return distance_matrix


def osrm_distance_matrix(coordinates, osrm_server):
    """
    Calculate a distance matrix using OSRM.
    
    Args:
        coordinates (list): List of dicts with 'lat' and 'lng' keys
        osrm_server (str): URL of OSRM server
        
    Returns:
        list: 2D matrix of distances in kilometers
    """
    # Prepare coordinates for OSRM request
    coords_str = ";".join([f"{c['lng']},{c['lat']}" for c in coordinates])
    
    # Build the URL for the OSRM request
    url = f"{osrm_server}/table/v1/driving/{coords_str}?annotations=distance"
    
    # Make the request
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        
        if 'distances' in data:
            # OSRM returns distances in meters, convert to kilometers
            distances = data['distances']
            n = len(distances)
            
            return [[distances[i][j] / 1000 for j in range(n)] for i in range(n)]
    
    # If OSRM request fails, throw an exception to fallback to haversine
    raise Exception(f"OSRM request failed with status {response.status_code}")

def dijkstra_shortest_path(graph, start, end):
    """
    Find the shortest path between two nodes in a graph using Dijkstra's algorithm.
    
    Args:
        graph (networkx.Graph): Graph representation
        start (int): Starting node
        end (int): Ending node
        
    Returns:
        tuple: (path, distance)
    """
    # Create a priority queue
    pq = PriorityQueue()
    pq.put((0, start))
    
    # Distance from start to node
    distances = {start: 0}
    # Previous node in optimal path
    previous = {start: None}
    
    while not pq.empty():
        # Get the node with the smallest distance
        current_distance, current_node = pq.get()
        
        # If we've reached the end, we're done
        if current_node == end:
            break
        
        # Skip if we've already found a better path
        if current_distance > distances.get(current_node, float('inf')):
            continue
        
        # Check all neighbors
        for neighbor, weight in graph[current_node].items():
            distance = current_distance + weight
            
            # If we found a better path, update
            if distance < distances.get(neighbor, float('inf')):
                distances[neighbor] = distance
                previous[neighbor] = current_node
                pq.put((distance, neighbor))
    
    # Reconstruct the path
    if end not in previous:
        return None, float('inf')  # No path exists
    
    path = []
    current = end
    
    while current is not None:
        path.append(current)
        current = previous[current]
    
    path.reverse()
    
    return path, distances[end]

def build_road_network(coordinates, distance_threshold=10.0):
    """
    Build a simple road network using coordinates.
    
    Args:
        coordinates (list): List of dicts with 'lat' and 'lng' keys
        distance_threshold (float): Maximum distance to consider for direct connections
        
    Returns:
        networkx.Graph: Graph representation of the road network
    """
    # Create an empty graph
    G = nx.Graph()
    
    # Add nodes
    for i in range(len(coordinates)):
        G.add_node(i, pos=(coordinates[i]['lng'], coordinates[i]['lat']))
    
    # Add edges (connect nodes within threshold distance)
    for i in range(len(coordinates)):
        for j in range(i + 1, len(coordinates)):
            lat1 = coordinates[i]['lat']
            lng1 = coordinates[i]['lng']
            lat2 = coordinates[j]['lat']
            lng2 = coordinates[j]['lng']
            
            distance = haversine_distance(lat1, lng1, lat2, lng2)
            
            if distance <= distance_threshold:
                G.add_edge(i, j, weight=distance)
    
    # Ensure the graph is connected
    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        
        # Connect the largest components
        for i in range(len(components) - 1):
            comp1 = list(components[i])
            comp2 = list(components[i + 1])
            
            # Find the closest pair between components
            min_dist = float('inf')
            best_pair = None
            
            for n1 in comp1:
                for n2 in comp2:
                    lat1 = coordinates[n1]['lat']
                    lng1 = coordinates[n1]['lng']
                    lat2 = coordinates[n2]['lat']
                    lng2 = coordinates[n2]['lng']
                    
                    dist = haversine_distance(lat1, lng1, lat2, lng2)
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_pair = (n1, n2)
            
            # Add the best edge
            if best_pair:
                G.add_edge(best_pair[0], best_pair[1], weight=min_dist)
    
    return G

def network_distance_matrix(coordinates):
    """
    Calculate distance matrix using a simple road network.
    
    Args:
        coordinates (list): List of dicts with 'lat' and 'lng' keys
        
    Returns:
        list: 2D matrix of distances in kilometers
    """
    # Build road network
    G = build_road_network(coordinates)
    
    # Calculate all pairs shortest paths
    n = len(coordinates)
    distance_matrix = [[0 for _ in range(n)] for _ in range(n)]
    
    for i in range(n):
        for j in range(i + 1, n):
            # Find shortest path
            path, distance = dijkstra_shortest_path(G, i, j)
            
            if path:
                # Multiply by a factor to account for road curvature
                road_factor = 1.3
                distance_matrix[i][j] = distance * road_factor
                distance_matrix[j][i] = distance * road_factor
            else:
                # Fallback to haversine if no path found
                lat1 = coordinates[i]['lat']
                lng1 = coordinates[i]['lng']
                lat2 = coordinates[j]['lat']
                lng2 = coordinates[j]['lng']
                
                direct_distance = haversine_distance(lat1, lng1, lat2, lng2)
                distance_matrix[i][j] = direct_distance * 1.3  # Apply same factor
                distance_matrix[j][i] = direct_distance * 1.3
    
    return distance_matrix