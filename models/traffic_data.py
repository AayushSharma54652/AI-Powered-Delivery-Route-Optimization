import requests
import json
import time
from datetime import datetime
import os
import pickle
import random
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cache for traffic data to minimize API calls
traffic_cache = {}
# Cache expiration time in seconds (5 minutes)
CACHE_EXPIRATION = 300

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

def get_overpass_traffic_data(bounds, cache_dir='data/traffic_cache'):
    """
    Get traffic information using OpenStreetMap's Overpass API.
    This fetches roads with traffic signals, speed limits, and other traffic features.
    
    Args:
        bounds (tuple): (min_lat, min_lon, max_lat, max_lon)
        cache_dir (str): Directory to store cache files
        
    Returns:
        dict: Traffic data for the bounding box
    """
    min_lat, min_lon, max_lat, max_lon = bounds
    
    # Create cache directory if it doesn't exist
    os.makedirs(cache_dir, exist_ok=True)
    
    # Create a cache key based on bounds
    cache_key = f"{min_lat:.4f}_{min_lon:.4f}_{max_lat:.4f}_{max_lon:.4f}"
    cache_file = os.path.join(cache_dir, f"traffic_{cache_key}.pkl")
    
    # Check if we have cached data that's not expired
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
                cache_time = cached_data.get('timestamp', 0)
                
                # Check if cache is still valid (less than CACHE_EXPIRATION seconds old)
                if time.time() - cache_time < CACHE_EXPIRATION:
                    logger.info(f"Using cached traffic data for {cache_key}")
                    return cached_data['data']
        except Exception as e:
            logger.warning(f"Error reading cache file: {e}")
    
    # Overpass API query for traffic-related data
    overpass_url = "https://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      way({min_lat},{min_lon},{max_lat},{max_lon})[highway][maxspeed];
      way({min_lat},{min_lon},{max_lat},{max_lon})[highway][lanes];
      node({min_lat},{min_lon},{max_lat},{max_lon})[highway=traffic_signals];
      way({min_lat},{min_lon},{max_lat},{max_lon})[highway][oneway=yes];
    );
    out body;
    >;
    out skel qt;
    """
    
    try:
        # Make the request with appropriate headers and timeout
        headers = {
            "User-Agent": "DeliveryRouteOptimizer/1.0",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        # Use a session to handle connection pooling
        session = requests.Session()
        response = session.post(overpass_url, data={"data": overpass_query}, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Process the response
            osm_data = response.json()
            
            # Extract relevant traffic information
            traffic_data = process_osm_traffic_data(osm_data)
            
            # Cache the results
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'timestamp': time.time(),
                    'data': traffic_data
                }, f)
            
            logger.info(f"Successfully fetched and cached traffic data for {cache_key}")
            return traffic_data
        else:
            logger.warning(f"Overpass API request failed with status {response.status_code}")
            
            # If API request fails, try to use an older cached version if available
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'rb') as f:
                        cached_data = pickle.load(f)
                        logger.info(f"Using older cached traffic data for {cache_key} due to API failure")
                        return cached_data['data']
                except Exception as e:
                    logger.warning(f"Error reading older cache file: {e}")
    
    except Exception as e:
        logger.error(f"Error fetching traffic data: {e}")
    
    # If we reach here, we couldn't get data from API or cache
    # Return simulated traffic data as a fallback
    return generate_simulated_traffic_data(bounds)

def process_osm_traffic_data(osm_data):
    """
    Process OpenStreetMap data to extract traffic information.
    
    Args:
        osm_data (dict): Raw OSM data from Overpass API
        
    Returns:
        dict: Processed traffic data
    """
    # Initialize traffic data structure
    traffic_data = {
        'traffic_signals': [],  # List of traffic signal locations
        'road_speeds': {},      # Dict of road id -> speed limit
        'congestion_areas': []  # List of areas with potential congestion
    }
    
    # Map to store node information
    nodes = {}
    
    # Extract node coordinates
    for element in osm_data.get('elements', []):
        if element.get('type') == 'node':
            node_id = element.get('id')
            nodes[node_id] = {
                'lat': element.get('lat'),
                'lon': element.get('lon')
            }
            
            # Check if this node is a traffic signal
            if element.get('tags', {}).get('highway') == 'traffic_signals':
                traffic_data['traffic_signals'].append({
                    'lat': element.get('lat'),
                    'lon': element.get('lon')
                })
    
    # Process ways (roads)
    for element in osm_data.get('elements', []):
        if element.get('type') == 'way' and 'highway' in element.get('tags', {}):
            way_id = element.get('id')
            tags = element.get('tags', {})
            
            # Get speed limit if available
            if 'maxspeed' in tags:
                try:
                    # Handle various formats of maxspeed (e.g., "50", "50 mph", etc.)
                    speed_str = tags['maxspeed'].split()[0]
                    speed = int(speed_str)
                    traffic_data['road_speeds'][way_id] = speed
                except (ValueError, IndexError):
                    # Default speed if parsing fails
                    traffic_data['road_speeds'][way_id] = 50
            
            # Identify potential congestion areas (roads with multiple lanes or low speed limits)
            is_congestion_area = False
            
            # Check for low speed limits
            if way_id in traffic_data['road_speeds'] and traffic_data['road_speeds'][way_id] < 30:
                is_congestion_area = True
            
            # Check for roads with 3+ lanes (often busy roads)
            if 'lanes' in tags:
                try:
                    lanes = int(tags['lanes'])
                    if lanes >= 3:
                        is_congestion_area = True
                except ValueError:
                    pass
            
            # If this is a congestion area, add coordinates of the way
            if is_congestion_area and 'nodes' in element:
                way_coords = []
                for node_id in element['nodes']:
                    if node_id in nodes:
                        way_coords.append({
                            'lat': nodes[node_id]['lat'], 
                            'lon': nodes[node_id]['lon']
                        })
                
                if way_coords:
                    traffic_data['congestion_areas'].append({
                        'way_id': way_id,
                        'coords': way_coords,
                        # Random congestion level between 0.2 and 0.8 (higher means slower)
                        'congestion_level': round(random.uniform(0.2, 0.8), 2)
                    })
    
    return traffic_data

def generate_simulated_traffic_data(bounds):
    """
    Generate simulated traffic data when real data is unavailable.
    
    Args:
        bounds (tuple): (min_lat, min_lon, max_lat, max_lon)
        
    Returns:
        dict: Simulated traffic data
    """
    min_lat, min_lon, max_lat, max_lon = bounds
    
    # Current hour (used to simulate time-of-day traffic patterns)
    current_hour = datetime.now().hour
    
    # Traffic is typically heavier during rush hours (7-9 AM and 4-6 PM)
    is_rush_hour = (7 <= current_hour <= 9) or (16 <= current_hour <= 18)
    
    # Determine day of week (weekend vs weekday)
    is_weekday = datetime.now().weekday() < 5
    
    # Generate number of congestion areas based on time of day
    if is_rush_hour and is_weekday:
        num_congestion_areas = random.randint(5, 10)
    elif is_weekday:
        num_congestion_areas = random.randint(2, 6)
    else:
        # Weekend
        num_congestion_areas = random.randint(1, 4)
    
    # Generate congestion areas
    congestion_areas = []
    for i in range(num_congestion_areas):
        # Random location within bounds
        center_lat = random.uniform(min_lat, max_lat)
        center_lon = random.uniform(min_lon, max_lon)
        
        # Size of congestion area (in degrees)
        size = random.uniform(0.002, 0.01)
        
        # Generate a small cluster of points to represent the congestion area
        num_points = random.randint(3, 8)
        coords = []
        for j in range(num_points):
            lat = center_lat + random.uniform(-size, size)
            lon = center_lon + random.uniform(-size, size)
            coords.append({'lat': lat, 'lon': lon})
        
        # Congestion level (higher means slower)
        # Rush hour congestion is worse
        if is_rush_hour and is_weekday:
            congestion_level = round(random.uniform(0.5, 0.9), 2)
        else:
            congestion_level = round(random.uniform(0.2, 0.6), 2)
        
        congestion_areas.append({
            'way_id': f"sim_{i}",
            'coords': coords,
            'congestion_level': congestion_level
        })
    
    # Generate simulated traffic signals
    num_signals = random.randint(5, 15)
    traffic_signals = []
    for i in range(num_signals):
        lat = random.uniform(min_lat, max_lat)
        lon = random.uniform(min_lon, max_lon)
        traffic_signals.append({'lat': lat, 'lon': lon})
    
    # Generate simulated road speeds
    road_speeds = {}
    for i in range(20):
        road_speeds[f"sim_road_{i}"] = random.choice([30, 40, 50, 60, 70, 80])
    
    return {
        'traffic_signals': traffic_signals,
        'road_speeds': road_speeds,
        'congestion_areas': congestion_areas,
        'is_simulated': True
    }

def calculate_traffic_factor(coord1, coord2, traffic_data):
    """
    Calculate a traffic factor to adjust travel time between two points.
    
    Args:
        coord1 (dict): Dictionary with 'lat' and 'lng' keys for point 1
        coord2 (dict): Dictionary with 'lat' and 'lng' keys for point 2
        traffic_data (dict): Traffic data from get_overpass_traffic_data
        
    Returns:
        float: Traffic factor (1.0 means no traffic, >1.0 means traffic slows travel)
    """
    # Default factor with no traffic
    base_factor = 1.0
    
    # Check for nearby traffic signals
    signal_factor = check_traffic_signals(coord1, coord2, traffic_data.get('traffic_signals', []))
    
    # Check for congestion areas
    congestion_factor = check_congestion_areas(coord1, coord2, traffic_data.get('congestion_areas', []))
    
    # Add time-of-day factor
    time_factor = get_time_of_day_factor()
    
    # Combine factors - we want traffic to slow things down by at most 2-3x
    # Use a weighted combination that prevents extreme values
    combined_factor = base_factor + (signal_factor * 0.2) + (congestion_factor * 0.6) + (time_factor * 0.2)
    
    # Ensure the factor is reasonable (between 1.0 and 3.0)
    return max(1.0, min(3.0, combined_factor))

def check_traffic_signals(coord1, coord2, traffic_signals):
    """
    Check if there are traffic signals along the route.
    
    Args:
        coord1, coord2: Coordinate dictionaries with 'lat' and 'lng' keys
        traffic_signals: List of traffic signal locations
        
    Returns:
        float: Factor representing delay from traffic signals
    """
    if not traffic_signals:
        return 0.0
    
    # Simplified approach: check if any signals are close to the straight line between points
    lat1, lon1 = coord1['lat'], coord1['lng']
    lat2, lon2 = coord2['lat'], coord2['lng']
    
    # Direct distance between the two points
    direct_distance = haversine_distance(lat1, lon1, lat2, lon2)
    
    # Check distance to each signal
    signal_count = 0
    for signal in traffic_signals:
        # Calculate distance from signal to the line between coord1 and coord2
        # This is a simplified approach - we're just checking if the signal is close to either point
        d1 = haversine_distance(lat1, lon1, signal['lat'], signal['lon'])
        d2 = haversine_distance(lat2, lon2, signal['lat'], signal['lon'])
        
        # If the signal is close to either point (within 100m), count it
        if d1 < 0.1 or d2 < 0.1:  # 0.1 km = 100m
            signal_count += 1
    
    # More signals = more delay
    if signal_count == 0:
        return 0.0
    elif signal_count == 1:
        return 0.2  # One signal adds 20% delay
    else:
        # Multiple signals cause more delay, but with diminishing returns
        return min(0.5, signal_count * 0.15)  # Cap at 50% delay

def check_congestion_areas(coord1, coord2, congestion_areas):
    """
    Check if the route passes through congestion areas.
    
    Args:
        coord1, coord2: Coordinate dictionaries with 'lat' and 'lng' keys
        congestion_areas: List of congestion area definitions
        
    Returns:
        float: Factor representing delay from congestion
    """
    if not congestion_areas:
        return 0.0
    
    lat1, lon1 = coord1['lat'], coord1['lng']
    lat2, lon2 = coord2['lat'], coord2['lng']
    
    # Direct distance between the two points
    direct_distance = haversine_distance(lat1, lon1, lat2, lon2)
    
    # Check if route is near any congestion areas
    max_congestion = 0.0
    for area in congestion_areas:
        # For each congestion area, check if any point is near our route
        for point in area['coords']:
            d1 = haversine_distance(lat1, lon1, point['lat'], point['lon'])
            d2 = haversine_distance(lat2, lon2, point['lat'], point['lon'])
            
            # If point is close to either endpoint or close to the route
            if d1 < 0.5 or d2 < 0.5 or (d1 + d2) < (direct_distance * 1.2):
                max_congestion = max(max_congestion, area['congestion_level'])
    
    return max_congestion

def get_time_of_day_factor():
    """
    Calculate traffic factor based on time of day.
    
    Returns:
        float: Time-of-day traffic factor
    """
    # Get current hour
    current_hour = datetime.now().hour
    
    # Define rush hours
    morning_rush = (7, 8, 9)
    evening_rush = (16, 17, 18)
    
    # Weekend or weekday
    is_weekend = datetime.now().weekday() >= 5
    
    if is_weekend:
        # Weekend traffic patterns
        if 10 <= current_hour <= 18:  # Shopping hours
            return 0.3
        else:
            return 0.1
    else:
        # Weekday traffic patterns
        if current_hour in morning_rush or current_hour in evening_rush:
            return 0.5  # Heavy rush hour traffic
        elif 10 <= current_hour <= 15:
            return 0.2  # Midday traffic
        elif 19 <= current_hour <= 21:
            return 0.2  # Evening traffic
        else:
            return 0.0  # Light traffic at other times
            
def apply_traffic_to_distance_matrix(distance_matrix, coordinates, bounds=None):
    """
    Apply traffic factors to a distance matrix.
    
    Args:
        distance_matrix (list): Original distance matrix
        coordinates (list): List of coordinate dictionaries with 'lat' and 'lng' keys
        bounds (tuple, optional): Bounding box (min_lat, min_lon, max_lat, max_lon)
        
    Returns:
        tuple: (travel_time_matrix, traffic_factors)
    """
    n = len(distance_matrix)
    travel_time_matrix = [[0 for _ in range(n)] for _ in range(n)]
    traffic_factors = [[1.0 for _ in range(n)] for _ in range(n)]
    
    # Calculate bounds if not provided
    if bounds is None:
        min_lat = min(coord['lat'] for coord in coordinates)
        min_lon = min(coord['lng'] for coord in coordinates)
        max_lat = max(coord['lat'] for coord in coordinates)
        max_lon = max(coord['lng'] for coord in coordinates)
        
        # Add a small buffer
        buffer = 0.05  # ~5km
        bounds = (min_lat - buffer, min_lon - buffer, max_lat + buffer, max_lon + buffer)
    
    # Get traffic data for the area
    traffic_data = get_overpass_traffic_data(bounds)
    
    # Apply traffic factors to each segment
    for i in range(n):
        for j in range(n):
            if i != j:
                # Get traffic factor for this segment
                traffic_factor = calculate_traffic_factor(coordinates[i], coordinates[j], traffic_data)
                traffic_factors[i][j] = traffic_factor
                
                # Apply to distance to get travel time
                # Assuming average speed without traffic is 30 km/h
                # This gives time in hours
                base_time = distance_matrix[i][j] / 30.0
                travel_time_matrix[i][j] = base_time * traffic_factor
            else:
                travel_time_matrix[i][j] = 0.0
    
    return travel_time_matrix, traffic_factors, traffic_data