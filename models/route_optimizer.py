import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta
import math

# Modified optimize_routes function to ensure vehicle_count is properly used

# Enhanced route_optimizer.py function
# Replace the optimize_routes function with this implementation

def optimize_routes(depot, locations, distance_matrix, vehicle_count=1, max_distance=None, clusters=None, vehicle_data=None):
    """
    Optimize delivery routes using Google OR-Tools.
    Enhanced to properly handle multiple vehicles with different vehicle types.
    
    Args:
        depot (dict): Depot location
        locations (list): List of delivery locations
        distance_matrix (list): 2D matrix of distances
        vehicle_count (int): Number of vehicles
        max_distance (float, optional): Maximum distance per vehicle
        clusters (list, optional): List of location clusters by vehicle
        vehicle_data (list, optional): Data about each vehicle
        
    Returns:
        list: Optimized routes
    """
    # Debug information
    print(f"Optimizing routes for {len(locations)} locations and {vehicle_count} vehicles")
    
    # Ensure vehicle_count is an integer
    vehicle_count = int(vehicle_count)
    
    # Prepare vehicle-specific data
    if not vehicle_data:
        # Create default vehicle data if not provided
        vehicle_data = [{
            'id': i,
            'type': 'van',
            'capacity': 1000,
            'weight': 2000
        } for i in range(vehicle_count)]
    
    # Check if using pre-assigned clusters
    using_clusters = clusters is not None and len(clusters) == vehicle_count
    
    # Create the routing index manager
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 
                                          vehicle_count, 
                                          0)  # 0 is the depot index
    
    # Create Routing Model
    routing = pywrapcp.RoutingModel(manager)
    
    # Create and register a transit callback
    def distance_callback(from_index, to_index):
        # Convert from routing variable Index to distance matrix NodeIndex
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_matrix[from_node][to_node] * 1000)  # Convert to integers for OR-Tools
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    
    # Define cost of each arc
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Add Distance constraint
    if max_distance:
        max_distance_meters = int(max_distance * 1000)  # Convert to meters
        dimension_name = 'Distance'
        routing.AddDimension(
            transit_callback_index,
            0,  # no slack
            max_distance_meters,  # vehicle maximum travel distance
            True,  # start cumul to zero
            dimension_name)
        distance_dimension = routing.GetDimensionOrDie(dimension_name)
        distance_dimension.SetGlobalSpanCostCoefficient(100)
    
    # Add time constraint for different vehicle speeds
    def time_callback(from_index, to_index):
        # Convert from routing variable Index to distance matrix NodeIndex
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        
        # Calculate time based on distance and vehicle speed
        vehicle_idx = routing.VehicleIndex(from_index)
        if vehicle_idx < len(vehicle_data):
            vehicle_type = vehicle_data[vehicle_idx].get('type', 'van')
            # Adjust speed based on vehicle type (km/h)
            speed = 35 if vehicle_type == 'truck' else 40 if vehicle_type == 'van' else 45  # car
        else:
            speed = 40  # Default speed
            
        # Convert to seconds (speed in km/h, distance in km)
        return int((distance_matrix[from_node][to_node] / speed) * 3600)
    
    time_callback_index = routing.RegisterTransitCallback(time_callback)
    
    # Add Time dimension
    routing.AddDimension(
        time_callback_index,
        60 * 60,  # Allow waiting time of up to 60 minutes
        24 * 60 * 60,  # Maximum time per vehicle (24 hours in seconds)
        False,  # Don't force start cumul to zero
        'Time')
    
    time_dimension = routing.GetDimensionOrDie('Time')
    
    # Add time window constraints if present
    has_time_windows = any(loc.get('time_window_start') for loc in locations)
    
    if has_time_windows:
        # Use 8:00 AM as the start time for the depot
        depot_start_time = datetime.strptime("8:00", "%H:%M")
        
        # Set time window for depot
        depot_index = manager.NodeToIndex(0)
        time_dimension.CumulVar(depot_index).SetRange(0, 24 * 60 * 60)  # Depot available 24 hours
        
        # Add time window constraints for each location
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
                    print(f"Setting time window for {location['name']}: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
                except Exception as e:
                    print(f"Error setting time window for {location['name']}: {e}")
    
    # Add vehicle capacity constraints
    def demand_callback(from_index):
        """Returns the demand of the node."""
        # The depot has no demand (0)
        from_node = manager.IndexToNode(from_index)
        return 1 if from_node > 0 else 0  # Each location has demand of 1 (simplification)
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        [vd.get('capacity', 100) for vd in vehicle_data],  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity')
    
    # Apply clustering constraints if provided
    if using_clusters:
        # For each vehicle, only allow it to visit nodes in its cluster
        for vehicle_id in range(vehicle_count):
            # Get this vehicle's cluster
            vehicle_cluster = clusters[vehicle_id]
            
            # For all nodes
            for node_idx in range(len(distance_matrix)):
                # Skip depot
                if node_idx == 0:
                    continue
                    
                # If this node is not in this vehicle's cluster, disallow it
                if (node_idx not in vehicle_cluster) and vehicle_cluster:
                    index = manager.NodeToIndex(node_idx)
                    routing.VehicleVar(index).RemoveValue(vehicle_id)
    
    # Setting first solution heuristic
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
        print("Solution found!")
        routes = []
        for vehicle_id in range(vehicle_count):
            # Get vehicle data
            v_data = vehicle_data[vehicle_id] if vehicle_id < len(vehicle_data) else {'id': vehicle_id, 'type': 'van'}
            
            route = {
                'vehicle_id': vehicle_id,
                'vehicle_type': v_data.get('type', 'van'),
                'stops': [],
                'total_distance': 0,
                'total_time': 0
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
            
            route_distance = 0
            route_time = 0
            previous_index = index
            has_stops = False
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                next_index = solution.Value(routing.NextVar(index))
                next_node_index = manager.IndexToNode(next_index)
                
                # Add distance between previous and current stops
                if node_index != next_node_index:
                    distance = distance_matrix[node_index][next_node_index]
                    route_distance += distance
                    
                    # Calculate time based on vehicle speed
                    vehicle_type = v_data.get('type', 'van')
                    speed = 35 if vehicle_type == 'truck' else 40 if vehicle_type == 'van' else 45  # car
                    time_hours = distance / speed
                    route_time += time_hours
                
                # Move to next stop
                index = next_index
                
                # Skip depot (node_index 0)
                if not routing.IsEnd(index) and next_node_index > 0:
                    location = locations[next_node_index - 1]  # Adjust index to match locations list
                    
                    # Add stop details
                    route['stops'].append({
                        'id': location['id'],
                        'name': location['name'],
                        'latitude': location['latitude'],
                        'longitude': location['longitude'],
                        'time_window_start': location.get('time_window_start'),
                        'time_window_end': location.get('time_window_end'),
                        'is_depot': False,
                        'leg_distance': distance if 'distance' in locals() else 0,
                        'leg_time': time_hours if 'time_hours' in locals() else 0
                    })
                    has_stops = True
            
            # Add depot as last stop to complete the route
            route['stops'].append({
                'id': depot['id'],
                'name': depot['name'],
                'latitude': depot['latitude'],
                'longitude': depot['longitude'],
                'is_depot': True
            })
            
            # Record total distance and time
            route['total_distance'] = route_distance
            route['total_time'] = route_time
            
            # Include route even if it has no stops (empty route)
            routes.append(route)
            
            # Print route info for debugging
            stop_names = [stop['name'] for stop in route['stops'] if not stop.get('is_depot', False)]
            print(f"Vehicle {vehicle_id} ({v_data.get('type', 'van')}): {len(stop_names)} stops - {', '.join(stop_names)}")
        
        return routes
    
    # If no solution found, create routes manually using clusters
    print("No solution found. Creating manual routes.")
    
    # If we have clusters, use them to create routes
    if using_clusters:
        manual_routes = []
        
        for vehicle_id in range(vehicle_count):
            # Get vehicle data
            v_data = vehicle_data[vehicle_id] if vehicle_id < len(vehicle_data) else {'id': vehicle_id, 'type': 'van'}
            
            # Get this vehicle's cluster
            cluster = clusters[vehicle_id] if vehicle_id < len(clusters) else []
            
            # Create a route just for this vehicle's cluster
            manual_route = {
                'vehicle_id': vehicle_id,
                'vehicle_type': v_data.get('type', 'van'),
                'stops': [
                    {
                        'id': depot['id'],
                        'name': depot['name'],
                        'latitude': depot['latitude'],
                        'longitude': depot['longitude'],
                        'is_depot': True
                    }
                ],
                'total_distance': 0,
                'total_time': 0
            }
            
            # Add this vehicle's locations in order of proximity to depot
            cluster_locations = []
            for index in cluster:
                if index > 0 and index <= len(locations):
                    cluster_locations.append(locations[index-1])
            
            # Sort locations by distance to depot for a simple TSP approach
            if cluster_locations:
                # Calculate distances from depot to each location
                depot_distances = []
                for loc in cluster_locations:
                    # Find index in original distance matrix
                    loc_index = 0
                    for i, orig_loc in enumerate(locations):
                        if orig_loc['id'] == loc['id']:
                            loc_index = i + 1  # +1 to account for depot
                            break
                    
                    dist = distance_matrix[0][loc_index]
                    depot_distances.append((loc, dist, loc_index))
                
                # Sort by distance (simple greedy approach)
                sorted_locations = []
                current_idx = 0  # Start at depot
                remaining = depot_distances.copy()
                
                while remaining:
                    # Find closest unvisited location
                    closest_idx = 0
                    closest_dist = float('inf')
                    for i, (loc, _, loc_idx) in enumerate(remaining):
                        dist = distance_matrix[current_idx][loc_idx]
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_idx = i
                    
                    # Add to route and update current position
                    closest = remaining.pop(closest_idx)
                    sorted_locations.append(closest[0])
                    current_idx = closest[2]
                
                # Add sorted locations to the route
                for location in sorted_locations:
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
            
            # Calculate the total distance manually
            total_distance = 0
            total_time = 0
            prev_idx = 0  # Start at depot
            
            for i, stop in enumerate(manual_route['stops'][1:], 1):  # Skip first depot
                # Find the location index in the distance matrix
                current_idx = 0  # Default to depot
                
                if not stop.get('is_depot', False):
                    for j, loc in enumerate(locations):
                        if loc['id'] == stop['id']:
                            current_idx = j + 1  # +1 to account for depot
                            break
                
                # Add distance for this leg
                leg_distance = distance_matrix[prev_idx][current_idx]
                total_distance += leg_distance
                
                # Calculate time based on vehicle speed
                vehicle_type = v_data.get('type', 'van')
                speed = 35 if vehicle_type == 'truck' else 40 if vehicle_type == 'van' else 45  # car
                leg_time = leg_distance / speed
                total_time += leg_time
                
                # Store leg details in the stop
                if i < len(manual_route['stops']):
                    manual_route['stops'][i]['leg_distance'] = leg_distance
                    manual_route['stops'][i]['leg_time'] = leg_time
                
                # Update previous index
                prev_idx = current_idx
            
            manual_route['total_distance'] = total_distance
            manual_route['total_time'] = total_time
            
            manual_routes.append(manual_route)
        
        return manual_routes
    
    # If no clusters or solution, distribute evenly
    manual_routes = []
    locations_per_vehicle = max(1, len(locations) // vehicle_count)
    
    for vehicle_id in range(vehicle_count):
        # Get vehicle data
        v_data = vehicle_data[vehicle_id] if vehicle_id < len(vehicle_data) else {'id': vehicle_id, 'type': 'van'}
        
        # Calculate start and end indices for this vehicle's locations
        start_idx = vehicle_id * locations_per_vehicle
        end_idx = min(start_idx + locations_per_vehicle, len(locations))
        
        # Create route for this vehicle
        manual_route = {
            'vehicle_id': vehicle_id,
            'vehicle_type': v_data.get('type', 'van'),
            'stops': [
                {
                    'id': depot['id'],
                    'name': depot['name'],
                    'latitude': depot['latitude'],
                    'longitude': depot['longitude'],
                    'is_depot': True
                }
            ],
            'total_distance': 0,
            'total_time': 0
        }
        
        # Add this vehicle's locations
        vehicle_locations = locations[start_idx:end_idx]
        for location in vehicle_locations:
            manual_route['stops'].append({
                'id': location['id'],
                'name': location['name'],
                'latitude': location['latitude'],
                'longitude': location['longitude'],
                'time_window_start': location.get('time_window_start'),
                'time_window_end': location.get('time_window_end'),
                'is_depot': False
            })
        
        # Add depot as last stop
        manual_route['stops'].append({
            'id': depot['id'],
            'name': depot['name'],
            'latitude': depot['latitude'],
            'longitude': depot['longitude'],
            'is_depot': True
        })
        
        # Calculate total distance and time
        total_distance = 0
        total_time = 0
        
        for i in range(len(manual_route['stops']) - 1):
            from_idx = 0  # Default to depot
            to_idx = 0  # Default to depot
            
            # Find indices in the distance matrix
            if i > 0 and not manual_route['stops'][i].get('is_depot', False):
                for j, loc in enumerate(locations):
                    if loc['id'] == manual_route['stops'][i]['id']:
                        from_idx = j + 1  # +1 to account for depot at index 0
                        break
            
            if i+1 > 0 and not manual_route['stops'][i+1].get('is_depot', False):
                for j, loc in enumerate(locations):
                    if loc['id'] == manual_route['stops'][i+1]['id']:
                        to_idx = j + 1  # +1 to account for depot at index 0
                        break
            
            # Add distance and time
            if from_idx < len(distance_matrix) and to_idx < len(distance_matrix):
                distance = distance_matrix[from_idx][to_idx]
                total_distance += distance
                
                # Calculate time based on vehicle type
                vehicle_type = v_data.get('type', 'van')
                speed = 35 if vehicle_type == 'truck' else 40 if vehicle_type == 'van' else 45  # car
                time = distance / speed
                total_time += time
                
                # Add leg info to stop
                if i+1 < len(manual_route['stops']):
                    manual_route['stops'][i+1]['leg_distance'] = distance
                    manual_route['stops'][i+1]['leg_time'] = time
        
        manual_route['total_distance'] = total_distance
        manual_route['total_time'] = total_time
        
        manual_routes.append(manual_route)
    
    return manual_routes


def optimize_routes_genetic(depot, locations, distance_matrix, vehicle_count=1, max_distance=None):
    """
    Alternative implementation using genetic algorithms via DEAP library.
    This can be used as a fallback or alternative to OR-Tools.
    
    Currently just a placeholder - you could implement this if OR-Tools doesn't meet your needs.
    """
    # Placeholder for genetic algorithm implementation
    return optimize_routes(depot, locations, distance_matrix, vehicle_count, max_distance)