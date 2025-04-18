from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta
import math
import json
import logging

# Import custom modules
from models.traffic_data import apply_traffic_to_distance_matrix

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Update traffic_optimizer.py to properly handle vehicle_data

def optimize_routes_with_traffic(depot, locations, distance_matrix, vehicle_count=1, max_distance=None, clusters=None, vehicle_data=None):
    """
    Optimize delivery routes using Google OR-Tools with real-time traffic data.
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
        tuple: (Optimized routes, Traffic info)
    """
    # Extract coordinates for traffic calculation
    coordinates = [{'lat': depot['latitude'], 'lng': depot['longitude']}]
    for loc in locations:
        coordinates.append({'lat': loc['latitude'], 'lng': loc['longitude']})
    
    # Apply traffic factors to get travel time matrix
    travel_time_matrix, traffic_factors, traffic_data = apply_traffic_to_distance_matrix(distance_matrix, coordinates)
    
    # Debug info
    print(f"Optimizing routes with traffic for {len(locations)} locations and {vehicle_count} vehicles")
    
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
    manager = pywrapcp.RoutingIndexManager(len(travel_time_matrix), 
                                          vehicle_count, 
                                          0)  # 0 is the depot index
    
    # Create Routing Model
    routing = pywrapcp.RoutingModel(manager)
    
    # Create and register transit callbacks
    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(distance_matrix[from_node][to_node] * 1000)  # Convert to meters
    
    def time_callback(from_index, to_index):
        """Returns the travel time between the two nodes with traffic."""
        # Convert from routing variable Index to time matrix NodeIndex
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Convert to seconds (travel_time_matrix is in hours)
        return int(travel_time_matrix[from_node][to_node] * 3600)
    
    distance_callback_index = routing.RegisterTransitCallback(distance_callback)
    time_callback_index = routing.RegisterTransitCallback(time_callback)
    
    # Define cost based on time (primary) and distance (secondary)
    routing.SetArcCostEvaluatorOfAllVehicles(time_callback_index)
    
    # Add Distance constraint
    if max_distance:
        max_distance_meters = int(max_distance * 1000)  # Convert to meters
        dimension_name = 'Distance'
        routing.AddDimension(
            distance_callback_index,
            0,  # no slack
            max_distance_meters,  # vehicle maximum travel distance
            True,  # start cumul to zero
            dimension_name)
        distance_dimension = routing.GetDimensionOrDie(dimension_name)
        distance_dimension.SetGlobalSpanCostCoefficient(100)
    
    # Add Time dimension
    time_dimension_name = 'Time'
    routing.AddDimension(
        time_callback_index,
        60 * 60,  # Allow waiting time of up to 60 minutes
        24 * 60 * 60,  # Maximum time per vehicle (24 hours in seconds)
        False,  # Don't force start cumul to zero
        time_dimension_name)
    
    time_dimension = routing.GetDimensionOrDie(time_dimension_name)
    
    # Add time window constraints if present
    depot_start_time = datetime.strptime("8:00", "%H:%M")  # 8:00 AM start
    has_time_windows = any(loc.get('time_window_start') for loc in locations)
    
    if has_time_windows:
        print("Setting up time window constraints")
        
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
                    print(f"Time window for {location['name']}: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
                except Exception as e:
                    print(f"Error setting time window for {location['name']}: {e}")
    
    # Add vehicle capacity constraints
    def demand_callback(from_index):
        """Returns the demand of the node."""
        # The depot has no demand (0)
        from_node = manager.IndexToNode(from_index)
        return 1 if from_node > 0 else 0  # Each location has demand of 1 (simplification)
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    
    # Get capacities for vehicles
    vehicle_capacities = [vd.get('capacity', 100) for vd in vehicle_data]
    if len(vehicle_capacities) < vehicle_count:
        # Fill with default capacity
        vehicle_capacities.extend([100] * (vehicle_count - len(vehicle_capacities)))
    
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        vehicle_capacities,  # vehicle maximum capacities
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
                'total_time': 0,
                'traffic_impact': 0  # New field to show traffic impact
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
            
            while not routing.IsEnd(index):
                index = solution.Value(routing.NextVar(index))
                
                if not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    
                    # Skip depot (node_index 0)
                    if node_index > 0:
                        location = locations[node_index - 1]  # Adjust index to match locations list
                        
                        # Get traffic factor for this leg
                        prev_node = manager.IndexToNode(previous_index)
                        tf = traffic_factors[prev_node][node_index]
                        
                        # Add stop details including traffic info
                        stop_info = {
                            'id': location['id'],
                            'name': location['name'],
                            'latitude': location['latitude'],
                            'longitude': location['longitude'],
                            'time_window_start': location.get('time_window_start'),
                            'time_window_end': location.get('time_window_end'),
                            'is_depot': False,
                            'traffic_factor': round(tf, 2)  # Add traffic factor info
                        }
                        
                        route['stops'].append(stop_info)
                        
                        # Add distance and time between previous and current stops
                        prev_node = manager.IndexToNode(previous_index)
                        distance = distance_matrix[prev_node][node_index]
                        route_distance += distance
                        
                        # Add time with traffic consideration
                        time = travel_time_matrix[prev_node][node_index]
                        route_time += time
                
                previous_index = index
            
            # Add depot as last stop to complete the route
            route['stops'].append({
                'id': depot['id'],
                'name': depot['name'],
                'latitude': depot['latitude'],
                'longitude': depot['longitude'],
                'is_depot': True
            })
            
            # Add final leg back to depot
            last_node = manager.IndexToNode(previous_index)
            distance = distance_matrix[last_node][0]  # 0 is depot index
            route_distance += distance
            
            time = travel_time_matrix[last_node][0]
            route_time += time
            
            # Record total distance and time
            route['total_distance'] = route_distance
            route['total_time'] = route_time
            
            # Calculate traffic impact (how much longer due to traffic)
            # Baseline time without traffic
            baseline_time = route_distance / 30  # Assuming 30 km/h without traffic
            traffic_delay = route_time - baseline_time
            route['traffic_impact'] = round(traffic_delay * 60, 1)  # Convert to minutes
            
            # Add route even if it has no stops (empty route)
            routes.append(route)
            
            # Print route info for debugging
            stop_names = [stop['name'] for stop in route['stops'] if not stop.get('is_depot', False)]
            print(f"Vehicle {vehicle_id} ({v_data.get('type', 'van')}): {len(stop_names)} stops - {', '.join(stop_names)}")
        
        # Add overall traffic information
        traffic_info = {
            'congestion_areas': len(traffic_data.get('congestion_areas', [])),
            'traffic_signals': len(traffic_data.get('traffic_signals', [])),
            'is_simulated': traffic_data.get('is_simulated', False),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return routes, traffic_info
    
    # If no solution found, fall back to the regular optimize_routes function
    print("No solution found with traffic optimization. Falling back to regular routing.")
    from models.route_optimizer import optimize_routes
    routes = optimize_routes(
        depot=depot,
        locations=locations,
        distance_matrix=distance_matrix,
        vehicle_count=vehicle_count,
        max_distance=max_distance,
        clusters=clusters,
        vehicle_data=vehicle_data
    )
    
    # Add traffic information
    traffic_info = {
        'congestion_areas': len(traffic_data.get('congestion_areas', [])),
        'traffic_signals': len(traffic_data.get('traffic_signals', [])),
        'is_simulated': traffic_data.get('is_simulated', True),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return routes, traffic_info