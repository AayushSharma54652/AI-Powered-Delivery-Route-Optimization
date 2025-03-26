import requests
import json
import time
import os
from math import radians, sin, cos, sqrt, atan2

# Cache for geocoded addresses to minimize API calls
geocode_cache = {}

def geocode_address(address):
    """
    Convert an address string to latitude and longitude using Nominatim API.
    
    Args:
        address (str): The address to geocode
        
    Returns:
        tuple: (latitude, longitude) or (None, None) if geocoding fails
    """
    # Check if address is already in cache
    if address in geocode_cache:
        return geocode_cache[address]
    
    # URL encode the address
    encoded_address = requests.utils.quote(address)
    
    # Use Nominatim API (free and open-source)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
    
    try:
        # Add appropriate headers
        headers = {
            "User-Agent": "DeliveryRouteOptimizer/1.0",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        # Make the request
        response = requests.get(url, headers=headers)
        
        # Check for rate limiting - Nominatim requests max 1 per second
        if response.status_code == 429:
            time.sleep(1)  # Wait and try again
            response = requests.get(url, headers=headers)
        
        # Parse response
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                latitude = float(data[0]["lat"])
                longitude = float(data[0]["lon"])
                
                # Cache the result
                geocode_cache[address] = (latitude, longitude)
                
                return latitude, longitude
    
    except Exception as e:
        print(f"Error geocoding address: {e}")
    
    # If we get here, geocoding failed
    return None, None

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

def batch_geocode(addresses):
    """
    Geocode multiple addresses with rate limiting.
    
    Args:
        addresses (list): List of address strings
        
    Returns:
        dict: Dictionary mapping addresses to (lat, lng) tuples
    """
    results = {}
    
    for address in addresses:
        # Skip if already cached
        if address in geocode_cache:
            results[address] = geocode_cache[address]
            continue
        
        # Geocode and respect rate limits
        lat, lng = geocode_address(address)
        results[address] = (lat, lng)
        
        # Wait to respect Nominatim's usage policy (1 request per second)
        time.sleep(1)
    
    return results

def reverse_geocode(lat, lng):
    """
    Convert latitude and longitude to an address.
    
    Args:
        lat (float): Latitude
        lng (float): Longitude
        
    Returns:
        str: Address string or None if reverse geocoding fails
    """
    # Use Nominatim API for reverse geocoding
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json"
    
    try:
        # Add appropriate headers
        headers = {
            "User-Agent": "DeliveryRouteOptimizer/1.0",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        # Make the request
        response = requests.get(url, headers=headers)
        
        # Check for rate limiting
        if response.status_code == 429:
            time.sleep(1)  # Wait and try again
            response = requests.get(url, headers=headers)
        
        # Parse response
        if response.status_code == 200:
            data = response.json()
            if 'display_name' in data:
                return data['display_name']
    
    except Exception as e:
        print(f"Error reverse geocoding: {e}")
    
    return None