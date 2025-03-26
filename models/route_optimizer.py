import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta
import math

def optimize_routes(depot, locations, distance_matrix, vehicle_count=1, max_distance=None, clusters=None):
    """
    Optimize delivery routes using Google OR-Tools.
    """
    # Debug information
    print(f"Optimizing routes for {len(locations)} locations and {vehicle_count} vehicles")
    print(f"Depot: {depot}")
    
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
    
    # Try solving with time windows first
    solution = None
    has_time_windows = any(loc.get('time_window_start') for loc in locations)
    
    if has_time_windows:
        # Add Time Window constraints
        print("Attempting to solve with time windows...")
        try:
            # Use 8:00 AM as the start time for the depot
            depot_start_time = datetime.strptime("8:00", "%H:%M")
            time_dimension_name = 'Time'
            # Assuming average speed of 30 km/h = 8.33 m/s
            speed = 8.33
            
            def time_callback(from_index, to_index):
                # Convert distance to time in seconds
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return int(distance_matrix[from_node][to_node] * 1000 / speed)
            
            time_callback_index = routing.RegisterTransitCallback(time_callback)
            routing.AddDimension(
                time_callback_index,
                60 * 60,  # Allow waiting time of up to 60 minutes
                24 * 60 * 60,  # Maximum time per vehicle (24 hours in seconds)
                False,  # Don't force start cumul to zero
                time_dimension_name)
            
            time_dimension = routing.GetDimensionOrDie(time_dimension_name)
            
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
                        print(f"Setting time window for {location['name']}: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')} ({start_seconds}-{end_seconds} seconds)")
                    except Exception as e:
                        print(f"Error setting time window for {location['name']}: {e}")
            
            # Set time window for depot
            index = manager.NodeToIndex(0)
            time_dimension.CumulVar(index).SetRange(0, 24 * 60 * 60)  # Depot available 24 hours
            
            # Setting first solution heuristic
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION)
            
            # Additional metaheuristics for better solutions
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
            search_parameters.time_limit.seconds = 10  # 10 seconds time limit
            
            # Solve the problem
            solution = routing.SolveWithParameters(search_parameters)
            
            if not solution:
                print("No solution found with time windows. Will try without time windows.")
        except Exception as e:
            print(f"Error solving with time windows: {e}")
            solution = None
    
    # If no solution with time windows, try without time windows
    if not solution:
        print("Solving without time windows...")
        
        # Create a new routing model without time windows
        routing = pywrapcp.RoutingModel(manager)
        
        # Register the distance callback again
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # Add Distance constraint again if needed
        if max_distance:
            max_distance_meters = int(max_distance * 1000)
            dimension_name = 'Distance'
            routing.AddDimension(
                transit_callback_index,
                0,
                max_distance_meters,
                True,
                dimension_name)
            distance_dimension = routing.GetDimensionOrDie(dimension_name)
            distance_dimension.SetGlobalSpanCostCoefficient(100)
        
        # Setting first solution heuristic
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        
        # Solve the problem
        solution = routing.SolveWithParameters(search_parameters)
    
    # Extract solution
    if solution:
        print("Solution found!")
        routes = []
        for vehicle_id in range(vehicle_count):
            route = {
                'vehicle_id': vehicle_id,
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
            previous_index = index
            
            while not routing.IsEnd(index):
                index = solution.Value(routing.NextVar(index))
                
                if not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    
                    # Skip depot (node_index 0)
                    if node_index > 0:
                        location = locations[node_index - 1]  # Adjust index to match locations list
                        
                        # Add stop details
                        route['stops'].append({
                            'id': location['id'],
                            'name': location['name'],
                            'latitude': location['latitude'],
                            'longitude': location['longitude'],
                            'time_window_start': location.get('time_window_start'),
                            'time_window_end': location.get('time_window_end'),
                            'is_depot': False
                        })
                        
                        # Add distance between previous and current stops
                        prev_node = manager.IndexToNode(previous_index)
                        distance = distance_matrix[prev_node][node_index]
                        route_distance += distance
                
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
            route_distance += distance_matrix[last_node][0]  # 0 is depot index
            
            # Calculate total time (assuming average speed of 30 km/h)
            route['total_distance'] = route_distance
            route['total_time'] = route_distance / 30
            
            # Only include routes with at least one stop (besides depot)
            if len(route['stops']) > 2:
                routes.append(route)
        
        # If we have routes, return them
        if routes:
            return routes
    
    # If no solution found or no valid routes, create a simple route manually
    print("No solution found. Creating a manual route.")
    manual_route = {
        'vehicle_id': 0,
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
    
    # Calculate the total distance manually
    total_distance = 0
    for i in range(len(manual_route['stops']) - 1):
        from_idx = 0 if i == 0 else i
        to_idx = 0 if i == len(manual_route['stops']) - 2 else i + 1
        if from_idx < len(distance_matrix) and to_idx < len(distance_matrix):
            total_distance += distance_matrix[from_idx][to_idx]
    
    manual_route['total_distance'] = total_distance
    manual_route['total_time'] = total_distance / 30
    
    return [manual_route]

def optimize_routes_genetic(depot, locations, distance_matrix, vehicle_count=1, max_distance=None):
    """
    Alternative implementation using genetic algorithms via DEAP library.
    This can be used as a fallback or alternative to OR-Tools.
    
    Currently just a placeholder - you could implement this if OR-Tools doesn't meet your needs.
    """
    # Placeholder for genetic algorithm implementation
    return optimize_routes(depot, locations, distance_matrix, vehicle_count, max_distance)