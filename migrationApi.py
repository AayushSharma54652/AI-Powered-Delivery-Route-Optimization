from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import os
import json
import yaml
from datetime import datetime, timedelta, time
import logging

# Import route optimization modules
from models.route_optimizer import optimize_routes
from models.time_predictor import predict_travel_time, TravelTimePredictor
from models.clustering import cluster_locations
from utils.geocoding import geocode_address, batch_geocode
from utils.distance_matrix import calculate_distance_matrix
from utils.data_processing import process_csv_data
from models.traffic_optimizer import optimize_routes_with_traffic
from models.traffic_data import get_overpass_traffic_data
from models.fuel_efficient_optimizer import optimize_routes_fuel_efficient
from models.vehicle_model import get_vehicle_efficiency_data, calculate_co2_emissions
from models.fuel_consumption_model import FuelConsumptionPredictor

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration
app.config['JSON_SORT_KEYS'] = False
app.config['SWAGGER_URL'] = '/api/docs'  # URL for exposing Swagger UI
app.config['API_URL'] = '/static/swagger.yaml'  # Our API spec file location
app.config['DATA_DIR'] = os.path.join(os.path.dirname(__file__), 'data')
app.config['STATIC_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static')

# Ensure directories exist
os.makedirs(app.config['DATA_DIR'], exist_ok=True)
os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(app.config['DATA_DIR'], 'api.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Register Swagger UI blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    app.config['SWAGGER_URL'],
    app.config['API_URL'],
    config={
        'app_name': "Route Optimizer API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=app.config['SWAGGER_URL'])

# Create a route to serve the swagger.yaml file
@app.route('/static/swagger.yaml')
def serve_swagger():
    return send_from_directory(app.config['STATIC_FOLDER'], 'swagger.yaml')

# API ENDPOINTS

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check API health"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/api/geocode', methods=['POST'])
def geocode_endpoint():
    """Geocode addresses to coordinates"""
    data = request.get_json()
    
    if not data or 'addresses' not in data:
        return jsonify({'error': 'No addresses provided'}), 400
    
    addresses = data['addresses']
    if not isinstance(addresses, list):
        addresses = [addresses]
    
    results = {}
    for address in addresses:
        lat, lng = geocode_address(address)
        if lat and lng:
            results[address] = {'latitude': lat, 'longitude': lng}
        else:
            results[address] = None
    
    return jsonify({
        'results': results,
        'count': {
            'total': len(addresses),
            'successful': sum(1 for r in results.values() if r is not None)
        }
    })

@app.route('/api/distance-matrix', methods=['POST'])
def distance_matrix_endpoint():
    """Calculate distance matrix between coordinates"""
    data = request.get_json()
    
    if not data or 'coordinates' not in data:
        return jsonify({'error': 'No coordinates provided'}), 400
    
    coordinates = data['coordinates']
    
    # Validate input format
    if not all('lat' in coord and 'lng' in coord for coord in coordinates):
        return jsonify({'error': 'Invalid coordinates format. Each coordinate should have lat and lng keys'}), 400
    
    matrix = calculate_distance_matrix(coordinates)
    
    return jsonify({
        'matrix': matrix,
        'size': len(matrix),
        'unit': 'kilometers'
    })

@app.route('/api/optimize-route', methods=['POST'])
def optimize_route_endpoint():
    """Optimize delivery routes"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Required fields
    if 'depot' not in data or 'locations' not in data:
        return jsonify({'error': 'Depot and locations are required'}), 400
    
    depot = data['depot']
    locations = data['locations']
    
    # Optional parameters
    vehicle_count = data.get('vehicle_count', 1)
    max_distance = data.get('max_distance')
    use_traffic = data.get('use_traffic', False)
    use_fuel_efficient = data.get('use_fuel_efficient', False)
    optimization_objective = data.get('optimization_objective', 'balanced')
    
    # Calculate distance matrix
    coordinates = [{'lat': depot['latitude'], 'lng': depot['longitude']}]
    for loc in locations:
        coordinates.append({'lat': loc['latitude'], 'lng': loc['longitude']})
    
    distance_matrix = calculate_distance_matrix(coordinates)
    
    # Optional: Cluster locations if there are multiple vehicles
    clusters = None
    if vehicle_count > 1:
        all_locations = [depot] + locations
        clusters = cluster_locations(all_locations, vehicle_count)
    
    # Choose optimization method based on parameters
    if use_fuel_efficient:
        # Get vehicle data
        vehicle_data = []
        for i in range(vehicle_count):
            vehicle_type = data.get(f'vehicle_type_{i}', 'van')
            vehicle_data.append(get_vehicle_efficiency_data(vehicle_type=vehicle_type))
        
        # Get traffic data if enabled
        traffic_data = None
        if use_traffic:
            min_lat = min(coord['lat'] for coord in coordinates)
            min_lon = min(coord['lng'] for coord in coordinates)
            max_lat = max(coord['lat'] for coord in coordinates)
            max_lon = max(coord['lng'] for coord in coordinates)
            
            bounds = (min_lat, min_lon, max_lat, max_lon)
            traffic_data = get_overpass_traffic_data(bounds)
        
        # Optimize with fuel efficiency
        try:
            routes = optimize_routes_fuel_efficient(
                depot=depot,
                locations=locations,
                distance_matrix=distance_matrix,
                vehicle_data=vehicle_data,
                traffic_data=traffic_data,
                vehicle_count=vehicle_count,
                max_distance=max_distance,
                clusters=clusters,
                optimization_objective=optimization_objective
            )
            
            return jsonify({
                'routes': routes,
                'optimization_type': 'fuel_efficient',
                'vehicle_count': vehicle_count,
                'total_locations': len(locations),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error optimizing fuel-efficient route: {str(e)}")
            return jsonify({'error': f'Failed to optimize route: {str(e)}'}), 500
        
    elif use_traffic:
        # Optimize with traffic awareness
        try:
            routes, traffic_info = optimize_routes_with_traffic(
                depot=depot,
                locations=locations,
                distance_matrix=distance_matrix,
                vehicle_count=vehicle_count,
                max_distance=max_distance,
                clusters=clusters
            )
            
            return jsonify({
                'routes': routes,
                'traffic_info': traffic_info,
                'optimization_type': 'traffic_aware',
                'vehicle_count': vehicle_count,
                'total_locations': len(locations),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error optimizing traffic-aware route: {str(e)}")
            return jsonify({'error': f'Failed to optimize route: {str(e)}'}), 500
    
    else:
        # Basic route optimization
        try:
            routes = optimize_routes(
                depot=depot,
                locations=locations,
                distance_matrix=distance_matrix,
                vehicle_count=vehicle_count,
                max_distance=max_distance,
                clusters=clusters
            )
            
            return jsonify({
                'routes': routes,
                'optimization_type': 'distance',
                'vehicle_count': vehicle_count,
                'total_locations': len(locations),
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error optimizing route: {str(e)}")
            return jsonify({'error': f'Failed to optimize route: {str(e)}'}), 500

@app.route('/api/predict-travel-time', methods=['POST'])
def predict_travel_time_endpoint():
    """Predict travel times based on distances, optionally considering time of day"""
    data = request.get_json()
    
    if not data or 'distances' not in data:
        return jsonify({'error': 'No distances provided'}), 400
    
    distances = data['distances']
    time_of_day = data.get('time_of_day')
    day_of_week = data.get('day_of_week')
    
    try:
        # If it's a distance matrix
        if isinstance(distances[0], list):
            time_matrix = predict_travel_time(distances, time_of_day, day_of_week)
            return jsonify({
                'time_matrix': time_matrix,
                'unit': 'hours'
            })
        else:
            # If it's a simple list of distances
            predictor = TravelTimePredictor()
            times = predictor.predict(distances, time_of_day, day_of_week)
                
            return jsonify({
                'times': times,
                'unit': 'hours'
            })
    except Exception as e:
        logger.error(f"Error predicting travel time: {str(e)}")
        return jsonify({'error': f'Failed to predict travel time: {str(e)}'}), 500

@app.route('/api/traffic-data', methods=['GET'])
def traffic_data_endpoint():
    """Get traffic data for a geographic area"""
    # Get bounds from URL parameters
    min_lat = request.args.get('min_lat', type=float)
    min_lon = request.args.get('min_lon', type=float)
    max_lat = request.args.get('max_lat', type=float)
    max_lon = request.args.get('max_lon', type=float)
    
    if not all([min_lat, min_lon, max_lat, max_lon]):
        return jsonify({'error': 'Missing required parameters (min_lat, min_lon, max_lat, max_lon)'}), 400
    
    bounds = (min_lat, min_lon, max_lat, max_lon)
    
    try:
        # Get traffic data
        traffic_data = get_overpass_traffic_data(bounds)
        
        return jsonify({
            'traffic_data': traffic_data,
            'bounds': bounds,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error fetching traffic data: {str(e)}")
        return jsonify({'error': f'Failed to fetch traffic data: {str(e)}'}), 500

@app.route('/api/fuel-consumption/predict', methods=['POST'])
def predict_fuel_consumption():
    """Predict fuel consumption for a route"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'distance' not in data or 'vehicle_type' not in data:
        return jsonify({'error': 'Missing required parameters (distance, vehicle_type)'}), 400
    
    try:
        # Initialize the predictor
        predictor = FuelConsumptionPredictor()
        
        # Predict fuel consumption
        fuel_consumption = predictor.predict(data)
        
        # Calculate CO2 emissions if fuel type is provided
        co2_emissions = None
        if 'fuel_type' in data:
            co2_emissions = calculate_co2_emissions(fuel_consumption, data['fuel_type'])
        
        return jsonify({
            'fuel_consumption': fuel_consumption,
            'unit': 'liters',
            'co2_emissions': co2_emissions,
            'co2_unit': 'kg' if co2_emissions else None
        })
    except Exception as e:
        logger.error(f"Error predicting fuel consumption: {str(e)}")
        return jsonify({'error': f'Failed to predict fuel consumption: {str(e)}'}), 500

@app.route('/api/fuel-consumption/record', methods=['POST'])
def record_fuel_consumption():
    """Record actual fuel consumption for model improvement"""
    data = request.get_json()
    
    if not data or 'route_id' not in data or 'vehicle_id' not in data or 'actual_fuel' not in data:
        return jsonify({'error': 'Missing required parameters (route_id, vehicle_id, actual_fuel)'}), 400
    
    try:
        # Optional metadata
        route_metadata = data.get('metadata', {})
        driver_id = data.get('driver_id')
        
        # Initialize a mock DB class for the API service
        class MockDB:
            def __init__(self):
                self.Model = type('Model', (), {'registry': type('Registry', (), {'_class_registry': {}})})
                self.session = type('Session', (), {'get': lambda self, cls, id: None})
                
        # Create fuel data collector
        from models.fuel_data_collector import FuelDataCollector
        collector = FuelDataCollector(MockDB())
        
        # In a real implementation, this would interact with a database
        # For the API service, we'll just return a success message
        logger.info(f"Recording fuel consumption: route_id={data['route_id']}, vehicle_id={data['vehicle_id']}, actual_fuel={data['actual_fuel']}")
        
        return jsonify({
            'message': 'Fuel consumption recorded successfully',
            'route_id': data['route_id'],
            'vehicle_id': data['vehicle_id'],
            'actual_fuel': data['actual_fuel'],
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error recording fuel consumption: {str(e)}")
        return jsonify({'error': f'Failed to record fuel consumption: {str(e)}'}), 500

@app.route('/api/clusters', methods=['POST'])
def cluster_locations_endpoint():
    """Cluster locations for multi-vehicle routing"""
    data = request.get_json()
    
    if not data or 'locations' not in data or 'num_clusters' not in data:
        return jsonify({'error': 'Missing required parameters (locations, num_clusters)'}), 400
    
    locations = data['locations']
    num_clusters = data['num_clusters']
    
    # Validate locations format
    if not all('latitude' in loc and 'longitude' in loc for loc in locations):
        return jsonify({'error': 'Invalid locations format. Each location should have latitude and longitude'}), 400
    
    try:
        # Perform clustering
        clusters = cluster_locations(locations, num_clusters)
        
        # Format response
        cluster_response = []
        for i, cluster in enumerate(clusters):
            cluster_response.append({
                'cluster_id': i,
                'location_indices': cluster,
                'size': len(cluster)
            })
        
        return jsonify({
            'clusters': cluster_response,
            'num_clusters': len(clusters),
            'total_locations': len(locations)
        })
    except Exception as e:
        logger.error(f"Error clustering locations: {str(e)}")
        return jsonify({'error': f'Failed to cluster locations: {str(e)}'}), 500

@app.route('/api/process-locations', methods=['POST'])
def process_locations():
    """Process location data from CSV or JSON"""
    try:
        if request.content_type and request.content_type.startswith('application/json'):
            data = request.get_json()
            
            if not data or 'locations' not in data:
                return jsonify({'error': 'No locations provided'}), 400
            
            locations = data['locations']
            
            # Geocode any addresses without coordinates
            for location in locations:
                if 'address' in location and ('latitude' not in location or 'longitude' not in location):
                    lat, lng = geocode_address(location['address'])
                    if lat and lng:
                        location['latitude'] = lat
                        location['longitude'] = lng
            
            return jsonify({
                'locations': locations,
                'count': len(locations),
                'geocoded': sum(1 for loc in locations if 'latitude' in loc and 'longitude' in loc)
            })
            
        elif request.content_type and request.content_type.startswith('multipart/form-data'):
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Empty file name'}), 400
            
            if file and file.filename.endswith('.csv'):
                locations = process_csv_data(file)
                
                # Geocode addresses if needed
                for location in locations:
                    if 'address' in location and ('latitude' not in location or 'longitude' not in location):
                        lat, lng = geocode_address(location['address'])
                        if lat and lng:
                            location['latitude'] = lat
                            location['longitude'] = lng
                
                return jsonify({
                    'locations': locations,
                    'count': len(locations),
                    'geocoded': sum(1 for loc in locations if 'latitude' in loc and 'longitude' in loc)
                })
            
            return jsonify({'error': 'Unsupported file format'}), 400
        
        return jsonify({'error': 'Unsupported content type'}), 400
    except Exception as e:
        logger.error(f"Error processing locations: {str(e)}")
        return jsonify({'error': f'Failed to process locations: {str(e)}'}), 500


@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    """Upload a CSV file containing location data"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty file name'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400
        
        # Process the CSV file
        locations = process_csv_data(file)
        
        # Geocode addresses if needed
        geocoded_count = 0
        for location in locations:
            # Convert datetime/time objects to strings
            for key, value in location.items():
                if isinstance(value, (datetime, time)):
                    location[key] = value.isoformat()
            
            if 'address' in location and ('latitude' not in location or 'longitude' not in location):
                lat, lng = geocode_address(location['address'])
                if lat and lng:
                    location['latitude'] = lat
                    location['longitude'] = lng
                    geocoded_count += 1
        
        # Save in memory for further processing
        logger.info(f"Successfully processed CSV with {len(locations)} locations, geocoded {geocoded_count}")
        
        return jsonify({
            'locations': locations,
            'count': len(locations),
            'geocoded': geocoded_count,
            'message': 'CSV imported successfully'
        })
        
    except Exception as e:
        logger.error(f"Error uploading CSV: {str(e)}")
        return jsonify({'error': f'Failed to process CSV file: {str(e)}'}), 500

# Function to create Swagger specification file
def create_swagger_spec():
    """Create the Swagger specification file from the provided YAML"""
    try:
        swagger_path = os.path.join(app.config['STATIC_FOLDER'], 'swagger.yaml')
        
        # Load the Swagger YAML content from the swagger_spec file
        with open('swagger.yaml', 'r') as f:
            swagger_content = f.read()
        
        # Write to the target location
        with open(swagger_path, 'w') as f:
            f.write(swagger_content)
        
        logger.info(f"Created Swagger specification file at {swagger_path}")
    except Exception as e:
        logger.error(f"Error creating Swagger specification: {str(e)}")
        # Create a basic version if loading fails
        create_basic_swagger_spec()

def create_basic_swagger_spec():
    """Create a basic Swagger specification if the full one fails to load"""
    swagger_path = os.path.join(app.config['STATIC_FOLDER'], 'swagger.yaml')
    
    # Basic swagger specification
    swagger_spec = {
        'openapi': '3.0.0',
        'info': {
            'title': 'Route Optimizer API',
            'description': 'API for optimizing delivery routes with AI/ML techniques',
            'version': '1.0.0'
        },
        'paths': {
            '/health': {
                'get': {
                    'summary': 'Health check',
                    'responses': {
                        '200': {
                            'description': 'API is healthy'
                        }
                    }
                }
            }
        }
    }
    
    # Write to file
    with open(swagger_path, 'w') as f:
        yaml.dump(swagger_spec, f, sort_keys=False)
    
    logger.info(f"Created basic Swagger specification at {swagger_path}")

# Run the application
if __name__ == '__main__':
    # Create static directory for swagger file if it doesn't exist
    os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)
    
    # Create swagger YAML file
    create_swagger_spec()
    
    # Start the Flask app
    logger.info("Starting Route Optimizer API service")
    app.run(debug=True, host='0.0.0.0', port=5000)