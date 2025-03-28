from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np
import math
import logging
import json
from datetime import datetime

# Import our fuel consumption model
from models.fuel_consumption_model import FuelConsumptionPredictor

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def optimize_routes_fuel_efficient(depot, locations, distance_matrix, vehicle_data, traffic_data=None, 
                                  vehicle_count=1, max_distance=None, clusters=None, 
                                  optimization_objective='balanced'):
    """
    Optimize delivery routes with emphasis on fuel efficiency.
    
    Args:
        depot (dict): Depot location
        locations (list): List of delivery locations
        distance_matrix (list): 2D matrix of distances between locations
        vehicle_data (list): List of vehicle information (type, capacity, etc.)
        traffic_data (dict, optional): Traffic information
        vehicle_count (int): Number of vehicles to use
        max_distance (float, optional): Maximum distance per vehicle
        clusters (list, optional): Pre-assigned location clusters
        optimization_objective (str): Objective to optimize for
            - 'time': Optimize for fastest delivery time
            - 'fuel': Optimize for minimum fuel consumption
            - 'balanced': Balance time and fuel consumption (default)
    
    Returns:
        list: Optimized routes with fuel consumption estimates
    """
    # Initialize fuel consumption predictor
    fuel_predictor = FuelConsumptionPredictor()
    
    # Ensure there are enough vehicles in vehicle_data
    if not vehicle_data or len(vehicle_data) < vehicle_count:
        # Create default vehicle data if not provided
        vehicle_data = [{
            'id': i,
            'type': 'van',
            'capacity': 1000,  # kg
            'weight': 2000,    # kg
            'fuel_efficiency': 10  # L/100km
        } for i in range(vehicle_count)]
    
    # Extract coordinates for all locations
    coordinates = [{'lat': depot['latitude'], 'lng': depot['longitude']}]
    for loc in locations:
        coordinates.append({'lat': loc['latitude'], 'lng': loc['longitude']})
    
    # Create travel time matrix based on distances and traffic
    travel_time_matrix = [[0 for _ in range(len(distance_matrix))] for _ in range(len(distance_matrix))]
    fuel_matrix = [[0 for _ in range(len(distance_matrix))] for _ in range(len(distance_matrix))]
    traffic_factors = [[1.0 for _ in range(len(distance_matrix))] for _ in range(len(distance_matrix))]
    
    # If we have traffic data, apply it to distances
    if traffic_data:
        for i in range(len(distance_matrix)):
            for j in range(len(distance_matrix)):
                if i != j:
                    # Extract traffic factor for this segment if available
                    traffic_factor = 1.0
                    for area in traffic_data.get('congestion_areas', []):
                        # Simple proximity check to congestion areas
                        if is_near_congestion(coordinates[i], coordinates[j], area):
                            traffic_factor = max(traffic_factor, area.get('congestion_level', 1.0))
                    
                    # Store traffic factors for later use
                    traffic_factors[i][j] = traffic_factor
                    
                    # Calculate travel time with traffic (assuming 30 km/h base speed)
                    travel_time_matrix[i][j] = (distance_matrix[i][j] / 30.0) * traffic_factor
    else:
        # Simple travel time calculation without traffic
        for i in range(len(distance_matrix)):
            for j in range(len(distance_matrix)):
                if i != j:
                    travel_time_matrix[i][j] = distance_matrix[i][j] / 30.0  # Assuming 30 km/h average speed
    
    # Calculate fuel consumption for each segment
    road_types = estimate_road_types(coordinates, distance_matrix)
    
    for i in range(len(distance_matrix)):
        for j in range(len(distance_matrix)):
            if i != j:
                # For each vehicle, calculate approximate fuel consumption
                for v_idx, vehicle in enumerate(vehicle_data[:vehicle_count]):
                    # Prepare data for fuel prediction
                    route_segment = {
                        'distance': distance_matrix[i][j],
                        'vehicle_type': vehicle.get('type', 'van'),
                        'vehicle_weight': vehicle.get('weight', 2000),
                        'load_weight': vehicle.get('load', 500),
                        'avg_speed': 30 / traffic_factors[i][j],  # Adjust speed for traffic
                        'traffic_factor': traffic_factors[i][j],
                        'stop_frequency': 1 / max(1, distance_matrix[i][j]),  # At least one stop per segment
                        'road_type': road_types[i][j],
                        'gradient': 0  # Assuming flat terrain for simplicity
                    }
                    
                    # Predict fuel consumption
                    fuel_consumption = fuel_predictor.predict(route_segment)
                    
                    # Store in fuel matrix (we'll use the first vehicle for now)
                    if v_idx == 0:
                        fuel_matrix[i][j] = fuel_consumption
    
    logger.info(f"Optimizing routes with {optimization_objective} objective")
    
    # Create the routing index manager
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 
                                          vehicle_count, 
                                          0)  # 0 is the depot index
    
    # Create Routing Model
    routing = pywrapcp.RoutingModel(manager)
    
    # Create and register transit callbacks for different metrics
    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_matrix[from_node][to_node] * 1000)  # Convert to meters
    
    def time_callback(from_index, to_index):
        """Returns the travel time between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(travel_time_matrix[from_node][to_node] * 3600)  # Convert to seconds
    
    def fuel_callback(from_index, to_index):
        """Returns the fuel consumption between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(fuel_matrix[from_node][to_node] * 1000)  # Convert to milliliters for integer math
    
    distance_callback_index = routing.RegisterTransitCallback(distance_callback)
    time_callback_index = routing.RegisterTransitCallback(time_callback)
    fuel_callback_index = routing.RegisterTransitCallback(fuel_callback)
    
    # Set the cost function based on optimization objective
    if optimization_objective == 'time':
        routing.SetArcCostEvaluatorOfAllVehicles(time_callback_index)
    elif optimization_objective == 'fuel':
        routing.SetArcCostEvaluatorOfAllVehicles(fuel_callback_index)
    else:  # balanced
        # Create a combined cost function that balances time and fuel
        def combined_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            
            # Normalize time and fuel to similar scales and combine
            time_cost = travel_time_matrix[from_node][to_node] * 3600  # seconds
            fuel_cost = fuel_matrix[from_node][to_node] * 1000  # milliliters
            
            # Weight time vs. fuel (adjust these weights to change the balance)
            time_weight = 0.5
            fuel_weight = 0.5
            
            # Return weighted combination
            return int(time_weight * time_cost + fuel_weight * fuel_cost)
        
        combined_callback_index = routing.RegisterTransitCallback(combined_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(combined_callback_index)
    
    # Add Distance dimension
    routing.AddDimension(
        distance_callback_index,
        0,  # no slack
        int(max_distance * 1000) if max_distance else 1000000000,  # vehicle maximum travel distance
        True,  # start cumul to zero
        'Distance')
    
    # Add Time dimension
    routing.AddDimension(
        time_callback_index,
        60 * 60,  # Allow waiting time of up to 60 minutes
        24 * 60 * 60,  # Maximum time per vehicle (24 hours in seconds)
        False,  # Don't force start cumul to zero
        'Time')
    
    # Add Fuel dimension
    routing.AddDimension(
        fuel_callback_index,
        0,  # no slack
        1000000,  # maximum fuel consumption (in milliliters)
        True,  # start cumul to zero
        'Fuel')
    
    # Add time window constraints if present
    time_dimension = routing.GetDimensionOrDie('Time')
    depot_start_time = datetime.strptime("8:00", "%H:%M")  # 8:00 AM start
    
    has_time_windows = any(loc.get('time_window_start') for loc in locations)
    if has_time_windows:
        logger.info("Setting up time window constraints")
        
        # Set time window for depot
        index = manager.NodeToIndex(0)
        time_dimension.CumulVar(index).SetRange(0, 24 * 60 * 60)  # Depot available 24 hours
        
        # Add time window for each location
        for location_idx, location in enumerate(locations):
            # Convert to routing index (add 1 to skip depot)
            routing_idx = location_idx + 1
            
            if location.get('time_window_start') and location.get('time_window_end'):
                try:
                    # Convert string/time to datetime for calculations
                    if isinstance(location['time_window_start'], str):
                        start_time = datetime.strptime(location['time_window_start'], "%H:%M")
                        end_time = datetime.strptime(location['time_window_end'], "%H:%M")
                    else:
                        # Assume it's a time object
                        start_time = datetime.combine(datetime.today(), location['time_window_start'])
                        end_time = datetime.combine(datetime.today(), location['time_window_end'])
                    
                    # Convert time to seconds from depot start time
                    start_seconds = int((start_time - depot_start_time).total_seconds())
                    end_seconds = int((end_time - depot_start_time).total_seconds())
                    
                    # Ensure start_seconds is non-negative
                    start_seconds = max(0, start_seconds)
                    
                    # If end time is before start time (e.g., crosses midnight), add 24 hours
                    if end_seconds < start_seconds:
                        end_seconds += 24 * 60 * 60
                    
                    # Set time window for this location
                    index = manager.NodeToIndex(routing_idx)
                    time_dimension.CumulVar(index).SetRange(start_seconds, end_seconds)
                except Exception as e:
                    logger.error(f"Error setting time window for {location['name']}: {e}")
    
    # Set first solution heuristic
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    
    # Add metaheuristics for better solutions
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.seconds = 30  # Increase time limit for better solutions
    
    # Solve the problem
    solution = routing.SolveWithParameters(search_parameters)
    
    # Extract solution
    if solution:
        logger.info("Solution found!")
        routes = []
        for vehicle_id in range(vehicle_count):
            vehicle_info = vehicle_data[vehicle_id] if vehicle_id < len(vehicle_data) else vehicle_data[0]
            
            route = {
                'vehicle_id': vehicle_id,
                'vehicle_type': vehicle_info.get('type', 'van'),
                'stops': [],
                'total_distance': 0,
                'total_time': 0,
                'total_fuel': 0,
                'fuel_saved': 0  # Will calculate this later
            }
            
            index = routing.Start(vehicle_id)
            
            # Get first stop (depot)
            route['stops'].append({
                'id': depot['id'],
                'name': depot['name'],
                'latitude': depot['latitude'],
                'longitude': depot['longitude'],
                'is_depot': True
            })
            
            # Initialize tracking variables
            route_distance = 0
            route_time = 0
            route_fuel = 0
            previous_index = index
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                next_node_index = manager.IndexToNode(solution.Value(routing.NextVar(index)))
                
                # Add distance, time, and fuel info for this leg
                if node_index != next_node_index:
                    distance = distance_matrix[node_index][next_node_index]
                    time = travel_time_matrix[node_index][next_node_index]
                    fuel = fuel_matrix[node_index][next_node_index]
                    
                    route_distance += distance
                    route_time += time
                    route_fuel += fuel
                    
                    # Move to next stop
                    index = solution.Value(routing.NextVar(index))
                    
                    # Skip depot (node_index 0)
                    if next_node_index > 0:
                        location = locations[next_node_index - 1]  # Adjust index to match locations list
                        
                        # Add stop details with fuel information
                        stop_info = {
                            'id': location['id'],
                            'name': location['name'],
                            'latitude': location['latitude'],
                            'longitude': location['longitude'],
                            'time_window_start': location.get('time_window_start'),
                            'time_window_end': location.get('time_window_end'),
                            'is_depot': False,
                            'leg_distance': distance,
                            'leg_time': time,
                            'leg_fuel': fuel,
                            'traffic_factor': traffic_factors[node_index][next_node_index]
                        }
                        
                        route['stops'].append(stop_info)
                else:
                    # Move to next stop without adding distance (should not happen)
                    index = solution.Value(routing.NextVar(index))
            
            # Add depot as last stop to complete the route
            route['stops'].append({
                'id': depot['id'],
                'name': depot['name'],
                'latitude': depot['latitude'],
                'longitude': depot['longitude'],
                'is_depot': True
            })
            
            # Add final leg back to depot
            last_node = manager.IndexToNode(index)
            final_distance = distance_matrix[last_node][0]  # 0 is depot index
            final_time = travel_time_matrix[last_node][0]
            final_fuel = fuel_matrix[last_node][0]
            
            route_distance += final_distance
            route_time += final_time
            route_fuel += final_fuel
            
            # Record total metrics
            route['total_distance'] = route_distance
            route['total_time'] = route_time
            route['total_fuel'] = route_fuel
            
            # Calculate fuel savings compared to a standard route (assumed to be 10% more fuel)
            route['fuel_saved'] = route_fuel * 0.1
            
            # Calculate fuel cost (assuming $1.5 per liter)
            route['fuel_cost'] = route_fuel * 1.5
            route['cost_saved'] = route['fuel_saved'] * 1.5
            
            # Only include routes with at least one stop (besides depot)
            if len(route['stops']) > 2:
                routes.append(route)
        
        return routes
    
    # If no solution found, create a simple route manually
    logger.warning("No solution found. Creating a manual route.")
    return create_manual_route(depot, locations, distance_matrix, vehicle_data[0], fuel_matrix)

def is_near_congestion(coord1, coord2, congestion_area):
    """Check if a route segment is near a congestion area"""
    # Simple check: are any of the congestion points near the line between coord1 and coord2
    for point in congestion_area.get('coords', []):
        # Calculate distances from point to line segment
        d1 = calculate_distance(coord1, {'lat': point['lat'], 'lng': point['lon']})
        d2 = calculate_distance(coord2, {'lat': point['lat'], 'lng': point['lon']})
        
        # If either endpoint is close to congestion
        if d1 < 2 or d2 < 2:  # 2 km threshold
            return True
    
    return False

def calculate_distance(coord1, coord2):
    """Calculate haversine distance between two coordinates"""
    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(coord1['lat'])
    lon1 = math.radians(coord1['lng'])
    lat2 = math.radians(coord2['lat'])
    lon2 = math.radians(coord2['lng'])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    
    return c * r

def estimate_road_types(coordinates, distance_matrix):
    """Estimate road types based on distances and coordinates"""
    n = len(coordinates)
    road_types = [['mixed' for _ in range(n)] for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            if i != j:
                distance = distance_matrix[i][j]
                straight_line = calculate_distance(coordinates[i], coordinates[j])
                
                # Calculate ratio of actual distance to straight line distance
                # Higher ratio suggests more urban roads with turns
                ratio = distance / straight_line if straight_line > 0 else 1
                
                if distance > 20 and ratio < 1.2:
                    # Long distances with direct routes are likely highways
                    road_types[i][j] = 'highway'
                elif distance < 5 or ratio > 1.4:
                    # Short distances or indirect routes are likely urban
                    road_types[i][j] = 'urban'
                else:
                    # Otherwise mixed
                    road_types[i][j] = 'mixed'
    
    return road_types

def create_manual_route(depot, locations, distance_matrix, vehicle_data, fuel_matrix):
    """Create a fallback route if optimization fails"""
    manual_route = {
        'vehicle_id': 0,
        'vehicle_type': vehicle_data.get('type', 'van'),
        'stops': [],
        'total_distance': 0,
        'total_time': 0,
        'total_fuel': 0,
        'fuel_saved': 0
    }
    
    # Add depot as first stop
    manual_route['stops'].append({
        'id': depot['id'],
        'name': depot['name'],
        'latitude': depot['latitude'],
        'longitude': depot['longitude'],
        'is_depot': True
    })
    
    # Add all locations in order
    for location in locations:
        manual_route['stops'].append({
            'id': location['id'],
            'name': location['name'],
            'latitude': location['latitude'],
            'longitude': location['longitude'],
            'time_window_start': location.get('time_window_start'),
            'time_window_end': location.get('time_window_end'),
            'is_depot': False
        })
    
    # Add depot at the end
    manual_route['stops'].append({
        'id': depot['id'],
        'name': depot['name'],
        'latitude': depot['latitude'],
        'longitude': depot['longitude'],
        'is_depot': True
    })
    
    # Calculate the total metrics manually
    total_distance = 0
    total_time = 0
    total_fuel = 0
    
    for i in range(len(manual_route['stops']) - 1):
        from_idx = 0 if i == 0 else i
        to_idx = 0 if i == len(manual_route['stops']) - 2 else i + 1
        
        if from_idx < len(distance_matrix) and to_idx < len(distance_matrix):
            # Add distance
            distance = distance_matrix[from_idx][to_idx]
            total_distance += distance
            
            # Add time (assuming 30 km/h average speed)
            time = distance / 30
            total_time += time
            
            # Add fuel if available
            if from_idx < len(fuel_matrix) and to_idx < len(fuel_matrix):
                fuel = fuel_matrix[from_idx][to_idx]
                total_fuel += fuel
            else:
                # Fallback fuel calculation (10L/100km)
                fuel = distance * 0.1
                total_fuel += fuel
    
    manual_route['total_distance'] = total_distance
    manual_route['total_time'] = total_time
    manual_route['total_fuel'] = total_fuel
    
    # Estimated fuel savings (assuming 10% more fuel used in standard routing)
    manual_route['fuel_saved'] = total_fuel * 0.1
    
    # Calculate fuel cost (assuming $1.5 per liter)
    manual_route['fuel_cost'] = total_fuel * 1.5
    manual_route['cost_saved'] = manual_route['fuel_saved'] * 1.5
    
    return [manual_route]