# utils/route_transfer_optimizer.py
import math
from datetime import datetime
from models.db_setup import db

def find_nearby_drivers(lat, lng, exclude_driver_id=None, radius_km=20, needed_vehicle_type=None):
    """
    Find drivers that are within a certain radius of the given coordinates.
    
    Args:
        lat (float): Latitude of the incident
        lng (float): Longitude of the incident
        exclude_driver_id (int, optional): Driver ID to exclude (usually the requesting driver)
        radius_km (float, optional): Radius in kilometers to search for drivers
        needed_vehicle_type (str, optional): Type of vehicle needed for the transfer
        
    Returns:
        list: List of Driver objects that are nearby and available
    """
    # Import Driver here to avoid circular imports - BUT using db.session.query instead of importing
    # This avoids the circular import problem
    
    # Find active drivers with a recent last_known_position
    # In a real system, you'd have more precise driver tracking
    now = datetime.utcnow()
    threshold = datetime.utcnow().replace(minute=now.minute - 30)  # Drivers active in the last 30 minutes
    
    # We need to use string identifiers for the models to avoid imports
    driver_model = db.Model.metadata.tables['driver']
    vehicle_model = db.Model.metadata.tables['vehicle']
    
    query = db.session.query(db.Model.registry._class_registry['Driver']).filter(
        db.Model.registry._class_registry['Driver'].is_active == True,
        db.Model.registry._class_registry['Driver'].last_login > threshold
    )
    
    if exclude_driver_id:
        query = query.filter(db.Model.registry._class_registry['Driver'].id != exclude_driver_id)
    
    # Filter based on vehicle type if needed
    if needed_vehicle_type:
        query = query.join(db.Model.registry._class_registry['Driver'].vehicle).filter(
            db.Model.registry._class_registry['Vehicle'].vehicle_type == needed_vehicle_type
        )
    
    potential_drivers = query.all()
    
    # Filter by distance (if lat/lng is available)
    nearby_drivers = []
    for driver in potential_drivers:
        if hasattr(driver, 'last_known_latitude') and hasattr(driver, 'last_known_longitude') and driver.last_known_latitude and driver.last_known_longitude:
            distance = calculate_distance(
                lat1=lat, 
                lng1=lng, 
                lat2=driver.last_known_latitude, 
                lng2=driver.last_known_longitude
            )
            
            if distance <= radius_km:
                driver.distance_km = distance
                nearby_drivers.append(driver)
    
    # Sort by distance
    nearby_drivers.sort(key=lambda d: getattr(d, 'distance_km', float('inf')))
    
    return nearby_drivers

def split_remaining_route(stops, driver_count=1):
    """
    Split remaining stops into optimal sub-routes for multiple drivers.
    
    Args:
        stops (list): List of DeliveryStop objects
        driver_count (int): Number of drivers to split the stops between
        
    Returns:
        list: List of lists, each containing stop IDs for a driver
    """
    if not stops:
        return []
    
    if driver_count <= 1 or len(stops) <= 1:
        return [stop.id for stop in stops]
    
    # Sort stops by stop_number to maintain route order
    sorted_stops = sorted(stops, key=lambda stop: stop.stop_number)
    
    # Simple splitting strategy - divide stops evenly
    # In a real system, you'd use a more sophisticated algorithm considering geography
    result = []
    stops_per_driver = max(1, len(sorted_stops) // driver_count)
    
    for i in range(0, driver_count):
        start_idx = i * stops_per_driver
        end_idx = start_idx + stops_per_driver if i < driver_count - 1 else len(sorted_stops)
        
        if start_idx < len(sorted_stops):
            driver_stops = [stop.id for stop in sorted_stops[start_idx:end_idx]]
            result.append(driver_stops)
    
    return result

def calculate_distance(lat1, lng1, lat2, lng2):
    """
    Calculate the great circle distance between two points on earth.
    
    Args:
        lat1, lng1: Coordinates of first point (decimal degrees)
        lat2, lng2: Coordinates of second point (decimal degrees)
        
    Returns:
        float: Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    
    return c * r