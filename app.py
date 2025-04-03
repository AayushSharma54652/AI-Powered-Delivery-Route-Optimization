from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, make_response, send_from_directory, logging
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import os
import json
from datetime import datetime, timedelta
# Custom modules
from models.route_optimizer import optimize_routes
from models.time_predictor import predict_travel_time
from models.clustering import cluster_locations
from utils.geocoding import geocode_address
from utils.distance_matrix import calculate_distance_matrix
from utils.data_processing import process_csv_data
from models.traffic_optimizer import optimize_routes_with_traffic
from models.traffic_data import get_overpass_traffic_data
from models.fuel_efficient_optimizer import optimize_routes_fuel_efficient
from models.vehicle_model import get_vehicle_efficiency_data, calculate_co2_emissions
from models.db_setup import db


data_dir = os.path.join(os.path.dirname(__file__), 'data')
if not os.path.exists(data_dir):
    os.makedirs(data_dir)


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-goes-here' 
app.config['JWT_SECRET_KEY'] = 'your-jwt-secret-key-here'  
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(data_dir, "locations.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# # Setup logging
# logging.basicConfig(level=logging.INFO, 
#                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)



# Authentication helper functions
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check if token is in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        # Check if token is in cookies
        if not token:
            token = request.cookies.get('token')
            
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            # Decode the token
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            
            # Check if token is expired
            exp_timestamp = data.get('exp', 0)
            if datetime.utcnow().timestamp() > exp_timestamp:
                return jsonify({'message': 'Token has expired! Please login again.'}), 401
            
            # Get the driver from database
            current_driver = Driver.query.filter_by(id=data['id']).first()
            
            # Check if driver exists
            if not current_driver:
                return jsonify({'message': 'Driver not found! User may have been deleted.'}), 401
                
            # Check if driver is active
            if not current_driver.is_active:
                return jsonify({'message': 'Driver account is inactive!'}), 403
                
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired! Please login again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token! Please login again.'}), 401
        except Exception as e:
            return jsonify({'message': f'Error processing token: {str(e)}'}), 401
            
        return f(current_driver, *args, **kwargs)
    
    return decorated


# Database models
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    time_window_start = db.Column(db.Time, nullable=True)
    time_window_end = db.Column(db.Time, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_distance = db.Column(db.Float, nullable=False)
    total_time = db.Column(db.Float, nullable=False)
    route_data = db.Column(db.Text, nullable=False)  
    traffic_data = db.Column(db.Text, nullable=True)

    total_fuel = db.Column(db.Float, nullable=True)  
    fuel_saved = db.Column(db.Float, nullable=True)  
    co2_saved = db.Column(db.Float, nullable=True)  
    optimization_type = db.Column(db.String(20), nullable=True)  
    actual_fuel = db.Column(db.Float, nullable=True) 
    fuel_accuracy = db.Column(db.Float, nullable=True) 
    

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_known_latitude = db.Column(db.Float, nullable=True)
    last_known_longitude = db.Column(db.Float, nullable=True)
    # Relationship with assigned routes
    assigned_routes = db.relationship('DriverRoute', back_populates='driver')
    
    # Relationship with vehicle
    vehicle = db.relationship('Vehicle', back_populates='drivers')
    fuel_efficiency_rating = db.Column(db.Float, nullable=True)  # Efficiency rating (lower is better)
    fuel_saved = db.Column(db.Float, nullable=True)  # Total fuel saved in liters
    routes_completed = db.Column(db.Integer, nullable=True)  # Count of completed routes
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'vehicle_id': self.vehicle_id,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'fuel_efficiency_rating': self.fuel_efficiency_rating,
            'fuel_saved': self.fuel_saved,
            'routes_completed': self.routes_completed
        }


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(20), nullable=False)  # car, van, truck, etc.
    capacity = db.Column(db.Float, nullable=False)  # capacity in cubic meters
    max_weight = db.Column(db.Float, nullable=False)  # max weight in kg
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with drivers
    drivers = db.relationship('Driver', back_populates='vehicle')
    fuel_consumption = db.Column(db.Float, nullable=True) 
    weight = db.Column(db.Float, nullable=True)          
    fuel_type = db.Column(db.String(20), default='diesel')  
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'license_plate': self.license_plate,
            'vehicle_type': self.vehicle_type,
            'capacity': self.capacity,
            'max_weight': self.max_weight,
            'is_active': self.is_active
        }

class DriverRoute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='assigned')  # assigned, in_progress, completed, cancelled
    
    # Relationships
    driver = db.relationship('Driver', back_populates='assigned_routes')
    route = db.relationship('Route', backref='driver_assignments')
    
    # Relationship with delivery stops
    delivery_stops = db.relationship('DeliveryStop', back_populates='driver_route')
    # Add to the DriverRoute class in app.py
    is_transfer = db.Column(db.Boolean, default=False)
    original_driver_route_id = db.Column(db.Integer, db.ForeignKey('driver_route.id'), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'driver_id': self.driver_id,
            'route_id': self.route_id,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status
        }

class DeliveryStop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_route_id = db.Column(db.Integer, db.ForeignKey('driver_route.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    stop_number = db.Column(db.Integer, nullable=False)
    planned_arrival_time = db.Column(db.DateTime, nullable=True)
    actual_arrival_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, arrived, completed, failed
    completion_notes = db.Column(db.Text, nullable=True)
    signature_image = db.Column(db.String(255), nullable=True)  # Path to signature image file
    proof_of_delivery = db.Column(db.String(255), nullable=True)  # Path to proof of delivery image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    driver_route = db.relationship('DriverRoute', back_populates='delivery_stops')
    location = db.relationship('Location', backref='delivery_stops')
    
    def to_dict(self):
        return {
            'id': self.id,
            'driver_route_id': self.driver_route_id,
            'location_id': self.location_id,
            'location_name': self.location.name,
            'location_address': self.location.address,
            'latitude': self.location.latitude,
            'longitude': self.location.longitude,
            'stop_number': self.stop_number,
            'planned_arrival_time': self.planned_arrival_time.isoformat() if self.planned_arrival_time else None,
            'actual_arrival_time': self.actual_arrival_time.isoformat() if self.actual_arrival_time else None,
            'status': self.status,
            'time_window_start': self.location.time_window_start.strftime('%H:%M') if self.location.time_window_start else None,
            'time_window_end': self.location.time_window_end.strftime('%H:%M') if self.location.time_window_end else None
        }
    
from models.route_incident import RouteIncident
from models.route_transfer import RouteTransfer
from utils.notification_service import Notification, send_driver_notification, notify_admin
from utils.route_transfer_optimizer import find_nearby_drivers, split_remaining_route, calculate_distance


RouteIncident.driver = db.relationship('Driver', backref='reported_incidents')
RouteIncident.driver_route = db.relationship('DriverRoute', backref='incidents')
RouteIncident.transfers = db.relationship('RouteTransfer', backref='incident', lazy='dynamic')

RouteTransfer.original_driver = db.relationship('Driver', foreign_keys=[RouteTransfer.original_driver_id], backref='transfers_out')
RouteTransfer.new_driver = db.relationship('Driver', foreign_keys=[RouteTransfer.new_driver_id], backref='transfers_in')
RouteTransfer.original_driver_route = db.relationship('DriverRoute', foreign_keys=[RouteTransfer.original_driver_route_id], backref='transfers_out')
RouteTransfer.new_driver_route = db.relationship('DriverRoute', foreign_keys=[RouteTransfer.new_driver_route_id], backref='transfers_in')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    locations = Location.query.all()

    print("LOCATIONS IN DATABASE:")
    for loc in locations:
        print(f"{loc.name} at {loc.latitude}, {loc.longitude}")

        
    routes = Route.query.order_by(Route.created_at.desc()).limit(5).all()
    return render_template('dashboard.html', locations=locations, routes=routes)

@app.route('/add_location', methods=['POST'])
def add_location():
    name = request.form.get('name')
    address = request.form.get('address')
    time_window_start = request.form.get('time_window_start')
    time_window_start_ampm = request.form.get('time_window_start_ampm', 'AM')
    time_window_end = request.form.get('time_window_end')
    time_window_end_ampm = request.form.get('time_window_end_ampm', 'PM')
    
    # Convert time from 12-hour to 24-hour format if needed
    if time_window_start and time_window_start_ampm:
        # Parse the time
        hour, minute = map(int, time_window_start.split(':'))
        
        # Adjust for PM (except for 12 PM which is already correct)
        if time_window_start_ampm == 'PM' and hour < 12:
            hour += 12
        # Adjust for 12 AM which should be 00
        elif time_window_start_ampm == 'AM' and hour == 12:
            hour = 0
            
        # Format back to string
        time_window_start = f"{hour:02d}:{minute:02d}"
    
    if time_window_end and time_window_end_ampm:
        # Parse the time
        hour, minute = map(int, time_window_end.split(':'))
        
        # Adjust for PM (except for 12 PM which is already correct)
        if time_window_end_ampm == 'PM' and hour < 12:
            hour += 12
        # Adjust for 12 AM which should be 00
        elif time_window_end_ampm == 'AM' and hour == 12:
            hour = 0
            
        # Format back to string
        time_window_end = f"{hour:02d}:{minute:02d}"
    
    # Geocode the address
    lat, lng = geocode_address(address)
    
    # Create new location
    if lat and lng:
        new_location = Location(
            name=name, 
            address=address, 
            latitude=lat, 
            longitude=lng,
            time_window_start=datetime.strptime(time_window_start, '%H:%M').time() if time_window_start else None,
            time_window_end=datetime.strptime(time_window_end, '%H:%M').time() if time_window_end else None
        )
        db.session.add(new_location)
        db.session.commit()
        return redirect(url_for('dashboard'))
    else:
        return "Failed to geocode address.", 400


@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    
    if file:
        locations = process_csv_data(file)
        for loc in locations:
            lat, lng = geocode_address(loc['address'])
            if lat and lng:
                new_location = Location(
                    name=loc['name'],
                    address=loc['address'],
                    latitude=lat,
                    longitude=lng,
                    time_window_start=loc.get('time_window_start'),
                    time_window_end=loc.get('time_window_end')
                )
                db.session.add(new_location)
        
        db.session.commit()
        return redirect(url_for('dashboard'))


# Enhanced multiple vehicle optimization for app.py
# Replace the optimize_route function with this implementation



@app.route('/optimize_route', methods=['POST'])
def optimize_route():
    """Optimized route calculator that properly handles multiple vehicles."""
    # Get form data
    depot_id = request.form.get('depot_id', type=int)
    vehicle_count = request.form.get('vehicle_count', type=int, default=1)
    max_distance = request.form.get('max_distance', type=float, default=None)
    
    # Validate inputs
    if vehicle_count is None or vehicle_count < 1:
        vehicle_count = 1
    
    print(f"Received request to optimize route with {vehicle_count} vehicles")
    
    # New parameter for traffic routing
    use_traffic = request.form.get('use_traffic', default='on') == 'on'
    
    # Get all locations
    locations = Location.query.all()
    
    # Find depot location
    depot = None
    delivery_locations = []
    
    for loc in locations:
        if loc.id == depot_id:
            depot = {
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude
            }
        else:
            delivery_locations.append({
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'time_window_start': loc.time_window_start.strftime('%H:%M') if loc.time_window_start else None,
                'time_window_end': loc.time_window_end.strftime('%H:%M') if loc.time_window_end else None
            })
    
    if not depot:
        return "Depot location not found", 400
    
    if not delivery_locations:
        return "No delivery locations found", 400
    
    # Calculate distance matrix
    coordinates = [{'lat': loc['latitude'], 'lng': loc['longitude']} for loc in [depot] + delivery_locations]
    distance_matrix = calculate_distance_matrix(coordinates)
    
    # Enhanced: Generate vehicle data for each vehicle
    vehicle_data = []
    for i in range(vehicle_count):
        vehicle_type = request.form.get(f'vehicle_type_{i}', 'van')
        vehicle_data.append({
            'id': i,
            'type': vehicle_type,
            # Get other vehicle properties from the form or use defaults
            'weight': 2500 if vehicle_type == 'van' else (1500 if vehicle_type == 'car' else 7500),
            'capacity': 8 if vehicle_type == 'van' else (2 if vehicle_type == 'car' else 30),
        })
    
    # Enhanced: Properly cluster locations for multiple vehicles
    clusters = None
    if vehicle_count > 1:
        try:
            print(f"Clustering {len(delivery_locations)} locations into {vehicle_count} clusters")
            # The enhanced cluster_locations function considers time windows and spatial distribution
            clusters = cluster_locations([depot] + delivery_locations, vehicle_count)
            
            # Apply balancing to improve cluster quality
            clusters = balance_clusters(clusters, [depot] + delivery_locations, distance_matrix)
            
            print(f"Created {len(clusters)} clusters:")
            for i, cluster in enumerate(clusters):
                cluster_locs = [delivery_locations[idx-1]['name'] for idx in cluster if idx-1 < len(delivery_locations)]
                print(f"  Cluster {i+1}: {len(cluster)} locations - {', '.join(cluster_locs)}")
        except Exception as e:
            print(f"Error in clustering: {e}")
            clusters = None
    
    # Optimize routes with or without traffic
    if use_traffic:
        # Use traffic-aware routing
        routes, traffic_info = optimize_routes_with_traffic(
            depot=depot,
            locations=delivery_locations,
            distance_matrix=distance_matrix,
            vehicle_count=vehicle_count,
            max_distance=max_distance,
            clusters=clusters,
            vehicle_data=vehicle_data  # Pass vehicle data to optimization
        )
        
        # Store traffic info with the route
        traffic_data_json = json.dumps(traffic_info)
    else:
        # Use classic routing without traffic
        routes = optimize_routes(
            depot=depot,
            locations=delivery_locations,
            distance_matrix=distance_matrix,
            vehicle_count=vehicle_count,
            max_distance=max_distance,
            clusters=clusters,
            vehicle_data=vehicle_data  # Pass vehicle data to optimization
        )
        traffic_data_json = "{}"
    
    # Check if we got expected number of routes
    if len(routes) < vehicle_count:
        print(f"Warning: Requested {vehicle_count} vehicles but only got {len(routes)} routes")
        # Ensure we have a route for each vehicle
        while len(routes) < vehicle_count:
            # Create an empty route for the missing vehicle
            empty_route = {
                'vehicle_id': len(routes),
                'vehicle_type': vehicle_data[len(routes)]['type'] if len(routes) < len(vehicle_data) else 'van',
                'stops': [
                    # Start at depot
                    {
                        'id': depot['id'],
                        'name': depot['name'],
                        'latitude': depot['latitude'],
                        'longitude': depot['longitude'],
                        'is_depot': True
                    },
                    # End at depot
                    {
                        'id': depot['id'],
                        'name': depot['name'],
                        'latitude': depot['latitude'],
                        'longitude': depot['longitude'],
                        'is_depot': True
                    }
                ],
                'total_distance': 0,
                'total_time': 0,
                'total_fuel': 0,
                'fuel_saved': 0
            }
            routes.append(empty_route)
    
    # Save route to database
    route_name = f"Route {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    total_distance = sum(route['total_distance'] for route in routes)
    total_time = sum(route['total_time'] for route in routes)
    
    new_route = Route(
        name=route_name,
        total_distance=total_distance,
        total_time=total_time,
        route_data=json.dumps(routes),
        traffic_data=traffic_data_json  # Add traffic data
    )
    db.session.add(new_route)
    db.session.commit()

    print("ROUTE DATA:", routes)
    for route in routes:
        print(f"Vehicle {route['vehicle_id']} ({route.get('vehicle_type', 'van')}) has {len(route['stops'])} stops")
        for stop in route['stops']:
            print(f"  - {stop['name']} at {stop['latitude']}, {stop['longitude']}")
    
    return redirect(url_for('view_route', route_id=new_route.id))




# Update the view_route function in app.py

@app.route('/routes/<int:route_id>')
def view_route(route_id):
    route = Route.query.get_or_404(route_id)
    route_data = json.loads(route.route_data)
    
    # Parse traffic data if available
    traffic_data = {}
    if route.traffic_data:
        try:
            traffic_data = json.loads(route.traffic_data)
        except:
            traffic_data = {}
    
    # Get active drivers and vehicles for route assignment
    drivers = Driver.query.filter_by(is_active=True).all()
    vehicles = Vehicle.query.filter_by(is_active=True).all()
    
    return render_template('routes.html', 
                          route=route, 
                          route_data=route_data, 
                          traffic_data=traffic_data,
                          drivers=drivers,
                          vehicles=vehicles)




@app.route('/analytics')
def analytics():
    routes = Route.query.all()
    route_stats = []
    
    for route in routes:
        route_data = json.loads(route.route_data)
        stats = {
            'name': route.name,
            'date': route.created_at.strftime('%Y-%m-%d'),
            'total_distance': route.total_distance,
            'total_time': route.total_time,
            'vehicle_count': len(route_data),
            'stop_count': sum(len(r['stops']) for r in route_data)
        }
        route_stats.append(stats)
    
    return render_template('analytics.html', route_stats=route_stats)

@app.route('/api/locations', methods=['GET'])
def api_locations():
    locations = Location.query.all()
    return jsonify([{
        'id': loc.id,
        'name': loc.name,
        'address': loc.address,
        'latitude': loc.latitude,
        'longitude': loc.longitude,
        'time_window_start': loc.time_window_start.strftime('%H:%M') if loc.time_window_start else None,
        'time_window_end': loc.time_window_end.strftime('%H:%M') if loc.time_window_end else None
    } for loc in locations])

@app.route('/api/routes/<int:route_id>', methods=['GET'])
def api_route(route_id):
    route = Route.query.get_or_404(route_id)
    return jsonify({
        'id': route.id,
        'name': route.name,
        'created_at': route.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'total_distance': route.total_distance,
        'total_time': route.total_time,
        'route_data': json.loads(route.route_data)
    })

@app.route('/api/traffic')
def api_traffic():
    # Get bounds from URL parameters
    min_lat = request.args.get('min_lat', type=float, default=40.7)
    min_lon = request.args.get('min_lon', type=float, default=-74.1)
    max_lat = request.args.get('max_lat', type=float, default=40.8)
    max_lon = request.args.get('max_lon', type=float, default=-73.9)
    
    bounds = (min_lat, min_lon, max_lat, max_lon)
    
    # Get traffic data
    traffic_data = get_overpass_traffic_data(bounds)
    
    return jsonify(traffic_data)

@app.route('/driver/login', methods=['POST'])
def driver_login():
    data = request.get_json()
    
    # Check if username and password are provided
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password are required'}), 400
        
    # Find the driver
    driver = Driver.query.filter_by(username=data['username']).first()
    
    # Check if driver exists and password is correct
    if not driver or not driver.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # If credentials are valid, generate a token
    token = jwt.encode({
        'id': driver.id,
        'exp': datetime.utcnow() + timedelta(hours=12)
    }, app.config['JWT_SECRET_KEY'])
    
    # Update last login time
    driver.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create response with token
    response = make_response(jsonify({
        'message': 'Login successful',
        'driver': driver.to_dict(),
        'token': token
    }))
    
    # Set cookie
    response.set_cookie('token', token, httponly=True, max_age=12*3600)
    
    return response

@app.route('/driver/logout', methods=['POST'])
@token_required
def driver_logout(current_driver):
    response = make_response(jsonify({'message': 'Logout successful'}))
    response.delete_cookie('token')
    return response

# Driver profile
@app.route('/driver/profile', methods=['GET'])
@token_required
def get_driver_profile(current_driver):
    return jsonify({
        'driver': current_driver.to_dict(),
        'vehicle': current_driver.vehicle.to_dict() if current_driver.vehicle else None
    })

# Driver routes
@app.route('/driver/routes', methods=['GET'])
@token_required
def get_driver_routes(current_driver):
    # Get all assigned routes for the driver
    driver_routes = DriverRoute.query.filter_by(driver_id=current_driver.id).order_by(DriverRoute.assigned_at.desc()).all()
    
    result = []
    for dr in driver_routes:
        route_data = json.loads(dr.route.route_data)
        
        # Find this driver's vehicle route (based on vehicle_id)
        vehicle_route = None
        for vr in route_data:
            if vr['vehicle_id'] == current_driver.vehicle_id:
                vehicle_route = vr
                break
        
        # If no specific vehicle route found, use the first one
        if not vehicle_route and route_data:
            vehicle_route = route_data[0]
            
        if vehicle_route:
            result.append({
                'driver_route': dr.to_dict(),
                'route_name': dr.route.name,
                'total_distance': vehicle_route.get('total_distance', 0),
                'total_time': vehicle_route.get('total_time', 0),
                'stops_count': len(vehicle_route.get('stops', [])) - 2 if vehicle_route.get('stops') else 0,
                'traffic_impact': vehicle_route.get('traffic_impact', 0)
            })
    
    return jsonify(result)

# Get specific route details
@app.route('/driver/routes/<int:driver_route_id>', methods=['GET'])
@token_required
def get_driver_route_details(current_driver, driver_route_id):
    # Find the specific driver route
    driver_route = DriverRoute.query.filter_by(id=driver_route_id, driver_id=current_driver.id).first()
    
    if not driver_route:
        return jsonify({'message': 'Route not found'}), 404
    
    # Get route data
    route_data = json.loads(driver_route.route.route_data)
    
    # Find vehicle route
    vehicle_route = None
    for vr in route_data:
        if vr['vehicle_id'] == current_driver.vehicle_id:
            vehicle_route = vr
            break
    
    # If no specific vehicle route found, use the first one
    if not vehicle_route and route_data:
        vehicle_route = route_data[0]
    
    if not vehicle_route:
        return jsonify({'message': 'Vehicle route not found'}), 404
    
    # Get delivery stops for this route
    delivery_stops = DeliveryStop.query.filter_by(driver_route_id=driver_route_id).order_by(DeliveryStop.stop_number).all()
    
    # Create response data
    result = {
        'driver_route': driver_route.to_dict(),
        'route_details': vehicle_route,
        'delivery_stops': [stop.to_dict() for stop in delivery_stops]
    }
    
    # Add traffic data if available
    if driver_route.route.traffic_data:
        result['traffic_data'] = json.loads(driver_route.route.traffic_data)
    
    return jsonify(result)

# Update driver route status
@app.route('/driver/routes/<int:driver_route_id>/status', methods=['PUT'])
@token_required
def update_driver_route_status(current_driver, driver_route_id):
    data = request.get_json()
    
    if not data or not data.get('status'):
        return jsonify({'message': 'Status is required'}), 400
    
    # Find the specific driver route
    driver_route = DriverRoute.query.filter_by(id=driver_route_id, driver_id=current_driver.id).first()
    
    if not driver_route:
        return jsonify({'message': 'Route not found'}), 404
    
    # Update status
    status = data['status']
    driver_route.status = status
    
    # Update timestamps
    if status == 'in_progress' and not driver_route.started_at:
        driver_route.started_at = datetime.utcnow()
    elif status == 'completed' and not driver_route.completed_at:
        driver_route.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Route status updated successfully',
        'driver_route': driver_route.to_dict()
    })

# Update delivery stop status
@app.route('/driver/stops/<int:stop_id>/status', methods=['PUT'])
@token_required
def update_delivery_stop_status(current_driver, stop_id):
    data = request.get_json()
    
    if not data or not data.get('status'):
        return jsonify({'message': 'Status is required'}), 400
    
    # Find the specific delivery stop and ensure it belongs to this driver
    stop = DeliveryStop.query.join(DriverRoute).filter(
        DeliveryStop.id == stop_id,
        DriverRoute.driver_id == current_driver.id
    ).first()
    
    if not stop:
        return jsonify({'message': 'Delivery stop not found'}), 404
    
    # Update stop status
    status = data['status']
    stop.status = status
    
    # Update arrival time if status is 'arrived'
    if status == 'arrived' and not stop.actual_arrival_time:
        stop.actual_arrival_time = datetime.utcnow()
    
    # Add completion notes if provided
    if data.get('notes'):
        stop.completion_notes = data['notes']
    
    # Save changes
    db.session.commit()
    
    # If all stops are completed, check if route should be marked as completed
    if status == 'completed' or status == 'failed':
        driver_route = stop.driver_route
        all_stops = DeliveryStop.query.filter_by(driver_route_id=driver_route.id).all()
        
        # Check if all stops are either completed or failed
        all_finished = all(s.status in ['completed', 'failed'] for s in all_stops)
        
        if all_finished and driver_route.status != 'completed':
            driver_route.status = 'completed'
            driver_route.completed_at = datetime.utcnow()
            db.session.commit()
    
    return jsonify({
        'message': 'Delivery stop status updated successfully',
        'stop': stop.to_dict()
    })

# Upload delivery proof (signature/photo)
@app.route('/driver/stops/<int:stop_id>/proof', methods=['POST'])
@token_required
def upload_delivery_proof(current_driver, stop_id):
    # Find the specific delivery stop and ensure it belongs to this driver
    stop = DeliveryStop.query.join(DriverRoute).filter(
        DeliveryStop.id == stop_id,
        DriverRoute.driver_id == current_driver.id
    ).first()
    
    if not stop:
        return jsonify({'message': 'Delivery stop not found'}), 404
    
    # Check if files are in the request
    if 'signature' not in request.files and 'photo' not in request.files:
        return jsonify({'message': 'No files provided'}), 400
    
    # Create directories if they don't exist
    proof_dir = os.path.join(app.root_path, 'static', 'proofs', str(current_driver.id))
    os.makedirs(proof_dir, exist_ok=True)
    
    # Handle signature upload
    if 'signature' in request.files:
        signature = request.files['signature']
        if signature.filename != '':
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"signature_{stop_id}_{timestamp}.png"
            filepath = os.path.join(proof_dir, filename)
            signature.save(filepath)
            
            # Save file path to database
            stop.signature_image = os.path.join('proofs', str(current_driver.id), filename)
    
    # Handle photo upload
    if 'photo' in request.files:
        photo = request.files['photo']
        if photo.filename != '':
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"photo_{stop_id}_{timestamp}.jpg"
            filepath = os.path.join(proof_dir, filename)
            photo.save(filepath)
            
            # Save file path to database
            stop.proof_of_delivery = os.path.join('proofs', str(current_driver.id), filename)
    
    # Save changes
    db.session.commit()
    
    return jsonify({
        'message': 'Delivery proof uploaded successfully',
        'stop': stop.to_dict()
    })

# Add these routes to app.py

# Admin routes for driver management
@app.route('/admin/drivers', methods=['GET'])
def admin_drivers():
    drivers = Driver.query.all()
    vehicles = Vehicle.query.all()
    return render_template('admin_drivers.html', drivers=drivers, vehicles=vehicles)

@app.route('/admin/drivers/add', methods=['POST'])
def add_driver():
    # Get form data
    username = request.form.get('username')
    password = request.form.get('password')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    vehicle_id = request.form.get('vehicle_id')
    
    # Validate required fields
    if not username or not password or not first_name or not last_name or not email or not phone:
        flash('All fields are required', 'danger')
        return redirect(url_for('admin_drivers'))
    
    # Check if username already exists
    if Driver.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('admin_drivers'))
    
    # Check if email already exists
    if Driver.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('admin_drivers'))
    
    # Create new driver
    new_driver = Driver(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        vehicle_id=vehicle_id if vehicle_id else None
    )
    
    # Set password
    new_driver.set_password(password)
    
    # Save to database
    db.session.add(new_driver)
    db.session.commit()
    
    flash('Driver added successfully', 'success')
    return redirect(url_for('admin_drivers'))

@app.route('/admin/drivers/<int:driver_id>/edit', methods=['POST'])
def edit_driver(driver_id):
    # Find driver
    driver = Driver.query.get_or_404(driver_id)
    
    # Update driver details
    driver.first_name = request.form.get('first_name', driver.first_name)
    driver.last_name = request.form.get('last_name', driver.last_name)
    driver.email = request.form.get('email', driver.email)
    driver.phone = request.form.get('phone', driver.phone)
    driver.vehicle_id = request.form.get('vehicle_id', driver.vehicle_id)
    driver.is_active = 'is_active' in request.form
    
    # Update password if provided
    new_password = request.form.get('password')
    if new_password:
        driver.set_password(new_password)
    
    # Save changes
    db.session.commit()
    
    flash('Driver updated successfully', 'success')
    return redirect(url_for('admin_drivers'))

@app.route('/admin/drivers/<int:driver_id>/delete', methods=['POST'])
def delete_driver(driver_id):
    # Find driver
    driver = Driver.query.get_or_404(driver_id)
    
    # Delete driver
    db.session.delete(driver)
    db.session.commit()
    
    flash('Driver deleted successfully', 'success')
    return redirect(url_for('admin_drivers'))

# Vehicle management routes
@app.route('/admin/vehicles', methods=['GET'])
def admin_vehicles():
    vehicles = Vehicle.query.all()
    return render_template('admin_vehicles.html', vehicles=vehicles)

@app.route('/admin/vehicles/add', methods=['POST'])
def add_vehicle():
    # Get form data
    name = request.form.get('name')
    license_plate = request.form.get('license_plate')
    vehicle_type = request.form.get('vehicle_type')
    capacity = request.form.get('capacity')
    max_weight = request.form.get('max_weight')
    
    # Validate required fields
    if not name or not license_plate or not vehicle_type or not capacity or not max_weight:
        flash('All fields are required', 'danger')
        return redirect(url_for('admin_vehicles'))
    
    # Check if license plate already exists
    if Vehicle.query.filter_by(license_plate=license_plate).first():
        flash('License plate already exists', 'danger')
        return redirect(url_for('admin_vehicles'))
    
    # Create new vehicle
    new_vehicle = Vehicle(
        name=name,
        license_plate=license_plate,
        vehicle_type=vehicle_type,
        capacity=float(capacity),
        max_weight=float(max_weight),
        is_active=True
    )
    
    # Save to database
    db.session.add(new_vehicle)
    db.session.commit()
    
    flash('Vehicle added successfully', 'success')
    return redirect(url_for('admin_vehicles'))

# Route assignment routes
@app.route('/admin/assign_route', methods=['POST'])
def assign_route_to_driver():
    route_id = request.form.get('route_id')
    driver_id = request.form.get('driver_id')
    
    if not route_id or not driver_id:
        flash('Route and driver are required', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if route exists
    route = Route.query.get(route_id)
    if not route:
        flash('Route not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if driver exists
    driver = Driver.query.get(driver_id)
    if not driver:
        flash('Driver not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Create driver route assignment
    driver_route = DriverRoute(
        driver_id=driver_id,
        route_id=route_id,
        status='assigned'
    )
    
    db.session.add(driver_route)
    db.session.commit()
    
    # Create delivery stops for this route
    route_data = json.loads(route.route_data)
    
    # Find appropriate vehicle route based on driver's vehicle
    vehicle_route = None
    for vr in route_data:
        # For simplicity, we'll use the first route if no vehicle match is found
        if not vehicle_route:
            vehicle_route = vr
        
        # If driver has a vehicle and it matches this route's vehicle ID, use this route
        if driver.vehicle_id and vr.get('vehicle_id') == driver.vehicle_id:
            vehicle_route = vr
            break
    
    # Create delivery stops from the route stops
    if vehicle_route and 'stops' in vehicle_route:
        stop_number = 1
        for stop in vehicle_route['stops']:
            # Skip depot stops (first and last)
            if stop.get('is_depot', False):
                continue
                
            # Get location
            location = Location.query.get(stop['id'])
            if not location:
                continue
                
            # Create delivery stop
            delivery_stop = DeliveryStop(
                driver_route_id=driver_route.id,
                location_id=location.id,
                stop_number=stop_number,
                status='pending'
            )
            
            db.session.add(delivery_stop)
            stop_number += 1
    
    db.session.commit()
    
    flash('Route assigned to driver successfully', 'success')
    return redirect(url_for('view_route', route_id=route_id))

# Add these routes to app.py

# Driver portal routes (UI routes)
@app.route('/driver/login')
def driver_login_page():
    return render_template('driver_login.html')

@app.route('/driver/dashboard')
def driver_dashboard():
    return render_template('driver_dashboard.html')

@app.route('/driver/route/<int:route_id>')
def driver_route_detail(route_id):
    return render_template('driver_route.html', route_id=route_id)

# Route to serve uploaded files
@app.route('/static/proofs/<path:filename>')
@token_required
def delivery_proof(current_driver, filename):
    # Extract driver ID from path
    path_parts = filename.split('/')
    if len(path_parts) < 2:
        return "File not found", 404
    
    driver_id = path_parts[0]
    
    # Check if the current driver is allowed to access this file
    if str(current_driver.id) != driver_id and not current_driver.is_admin:
        return "Unauthorized", 403
    
    return send_from_directory(os.path.join(app.root_path, 'static', 'proofs'), filename)


# Add these imports to the top of app.py
from models.fuel_efficient_optimizer import optimize_routes_fuel_efficient
from models.vehicle_model import get_vehicle_efficiency_data, calculate_co2_emissions

# Add this new route to app.py
@app.route('/optimize_route_fuel_efficient', methods=['POST'])
def optimize_route_fuel_efficient():
    """
    Optimize delivery routes with emphasis on fuel efficiency.
    """
    # Get form data
    depot_id = request.form.get('depot_id', type=int)
    vehicle_count = request.form.get('vehicle_count', type=int, default=1)
    max_distance = request.form.get('max_distance', type=float, default=None)
    optimization_objective = request.form.get('optimization_objective', default='balanced')
    
    # Optional parameters for vehicle selection
    vehicle_ids = request.form.getlist('vehicle_ids')
    
    # Get all locations
    locations = Location.query.all()
    
    # Find depot location
    depot = None
    delivery_locations = []
    
    for loc in locations:
        if loc.id == depot_id:
            depot = {
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude
            }
        else:
            delivery_locations.append({
                'id': loc.id,
                'name': loc.name,
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'time_window_start': loc.time_window_start.strftime('%H:%M') if loc.time_window_start else None,
                'time_window_end': loc.time_window_end.strftime('%H:%M') if loc.time_window_end else None
            })
    
    if not depot:
        return "Depot location not found", 400
    
    # Calculate distance matrix
    coordinates = [{'lat': loc['latitude'], 'lng': loc['longitude']} for loc in [depot] + delivery_locations]
    distance_matrix = calculate_distance_matrix(coordinates)
    
    # Get traffic data if enabled
    use_traffic = request.form.get('use_traffic', default='on') == 'on'
    traffic_data = None
    
    if use_traffic:
        # Get bounds from coordinates
        min_lat = min(coord['lat'] for coord in coordinates)
        min_lon = min(coord['lng'] for coord in coordinates)
        max_lat = max(coord['lat'] for coord in coordinates)
        max_lon = max(coord['lng'] for coord in coordinates)
        
        bounds = (min_lat, min_lon, max_lat, max_lon)
        traffic_data = get_overpass_traffic_data(bounds)
    
    # Get vehicle data
    vehicle_data = []
    
    if vehicle_ids:
        # If specific vehicles are selected, use their data
        for v_id in vehicle_ids:
            vehicle_data.append(get_vehicle_efficiency_data(vehicle_id=int(v_id), db=db))
    else:
        # Otherwise use default vehicles
        for i in range(vehicle_count):
            vehicle_type = request.form.get(f'vehicle_type_{i}', default='van')
            vehicle_data.append(get_vehicle_efficiency_data(vehicle_type=vehicle_type))
    
    # Optional: Cluster locations if there are multiple vehicles
    clusters = None
    if vehicle_count > 1:
        clusters = cluster_locations([depot] + delivery_locations, vehicle_count)
    
    # Optimize routes with fuel efficiency
    routes = optimize_routes_fuel_efficient(
        depot=depot,
        locations=delivery_locations,
        distance_matrix=distance_matrix,
        vehicle_data=vehicle_data,
        traffic_data=traffic_data,
        vehicle_count=vehicle_count,
        max_distance=max_distance,
        clusters=clusters,
        optimization_objective=optimization_objective
    )
    
    # Calculate total metrics
    total_distance = sum(route['total_distance'] for route in routes)
    total_time = sum(route['total_time'] for route in routes)
    total_fuel = sum(route['total_fuel'] for route in routes)
    total_fuel_saved = sum(route['fuel_saved'] for route in routes)
    
    # Calculate CO2 savings
    co2_saved = calculate_co2_emissions(total_fuel_saved)
    
    # Generate a formatted route name
    route_name = f"Fuel-Efficient Route {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    # Save route to database
    new_route = Route(
        name=route_name,
        total_distance=total_distance,
        total_time=total_time,
        route_data=json.dumps(routes),
        traffic_data=json.dumps(traffic_data) if traffic_data else "{}"
    )
    
    # Add fuel information to route (may need to extend your Route model)
    new_route.total_fuel = total_fuel
    new_route.fuel_saved = total_fuel_saved
    new_route.co2_saved = co2_saved
    
    db.session.add(new_route)
    db.session.commit()

    print("FUEL-EFFICIENT ROUTE DATA:", routes)
    for route in routes:
        print(f"Vehicle {route['vehicle_id']} ({route['vehicle_type']}) has {len(route['stops'])} stops")
        print(f"  - Total Distance: {route['total_distance']:.2f} km")
        print(f"  - Total Time: {route['total_time']:.2f} hours")
        print(f"  - Total Fuel: {route['total_fuel']:.2f} liters")
        print(f"  - Fuel Saved: {route['fuel_saved']:.2f} liters")
        print(f"  - Cost Saved: ${route['cost_saved']:.2f}")
    
    # Redirect to the route details page
    return redirect(url_for('view_route', route_id=new_route.id))

# Add this endpoint to your app.py file

@app.route('/api/routes/<int:route_id>/complete', methods=['POST'])
@token_required  # If using driver authentication
def complete_route(current_driver, route_id):
    """
    Record route completion with actual fuel consumption data.
    This allows the system to improve its fuel prediction model over time.
    """
    data = request.get_json()
    
    # Validate required fields
    if not data or 'actual_fuel' not in data:
        return jsonify({'message': 'Actual fuel consumption is required'}), 400
    
    # Get route
    route = Route.query.get_or_404(route_id)
    
    # Get driver assignment if needed
    driver_route = None
    if current_driver:
        driver_route = DriverRoute.query.filter_by(
            route_id=route_id, 
            driver_id=current_driver.id
        ).first()
    
    # Get vehicle info
    vehicle_id = data.get('vehicle_id')
    if not vehicle_id and current_driver and current_driver.vehicle_id:
        vehicle_id = current_driver.vehicle_id
    
    # If still no vehicle_id, try to get from driver_route
    if not vehicle_id and driver_route:
        # Extract vehicle ID from route data
        route_data = json.loads(route.route_data)
        for vr in route_data:
            if 'vehicle_id' in vr:
                vehicle_id = vr['vehicle_id']
                break
    
    # If still no vehicle, use a default ID
    if not vehicle_id:
        vehicle_id = 1  # Default vehicle
    
    # Collect metadata about the route
    route_metadata = {
        'load_weight': data.get('load_weight', 0),
        'avg_speed': data.get('avg_speed', 30),
        'traffic_factor': data.get('traffic_factor', 1.0),
        'road_type': data.get('road_type', 'mixed'),
        'temperature': data.get('temperature', 25),
        'weather_conditions': data.get('weather', 'clear'),
        'driver_efficiency': data.get('driver_efficiency', 1.0)
    }
    
    try:
        # Initialize the collector with the current db instance
        from models.fuel_data_collector import FuelDataCollector
        collector = FuelDataCollector(db)
        
        # Record actual fuel consumption
        success = collector.record_actual_fuel_consumption(
            route_id=route_id,
            vehicle_id=vehicle_id,
            actual_fuel=float(data['actual_fuel']),
            route_metadata=route_metadata,
            driver_id=current_driver.id if current_driver else None
        )
        
        if success:
            # Try to retrain the model if we have enough data
            collector.retrain_model()
            
            # If there's a driver_route, update its status
            if driver_route and driver_route.status != 'completed':
                driver_route.status = 'completed'
                driver_route.completed_at = datetime.utcnow()
                db.session.commit()
            
            return jsonify({
                'message': 'Route completed and fuel data recorded successfully',
                'route_id': route_id,
                'actual_fuel': data['actual_fuel']
            }), 200
        else:
            return jsonify({'message': 'Failed to record fuel data'}), 500
    
    except Exception as e:
        return jsonify({'message': f'Error: {str(e)}'}), 500



# Add this endpoint to get fuel prediction accuracy metrics
@app.route('/api/fuel/accuracy', methods=['GET'])
def get_fuel_accuracy_metrics():
    """Get metrics on fuel prediction accuracy based on collected data."""
    try:
        # Import the FuelDataCollector
        from models.fuel_data_collector import FuelDataCollector
        
        # Initialize the collector with the current db instance
        collector = FuelDataCollector(db)
        
        # Get accuracy metrics
        metrics = collector.analyze_prediction_accuracy()
        
        return jsonify(metrics), 200
    
    except Exception as e:
        logger.error(f"Error in get_fuel_accuracy_metrics API: {e}")
        # Return empty metrics instead of default sample data
        return jsonify({
            'record_count': 0,
            'no_data': True,
            'error': str(e)
        }), 200

@app.route('/api/drivers/efficiency', methods=['GET'])
def get_driver_efficiency():
    """Get driver efficiency rankings based on actual fuel consumption."""
    try:
        # Import the FuelDataCollector
        from models.fuel_data_collector import FuelDataCollector
        
        # Initialize the collector with the current db instance
        collector = FuelDataCollector(db)
        
        # Get driver rankings
        rankings = collector.get_driver_efficiency_ranking()
        
        return jsonify(rankings), 200
    
    except Exception as e:
        logger.error(f"Error in get_driver_efficiency API: {e}")
        # Return empty list instead of sample data
        return jsonify([]), 200


@app.route('/fuel_analytics')
def fuel_analytics_dashboard():
    """View the fuel efficiency analytics dashboard."""
    return render_template('fuel_analytics.html')



# Report an incident during route execution
@app.route('/api/driver/incidents', methods=['POST'])
@token_required
def report_incident(current_driver):
    data = request.get_json()
    
    # Validate request
    if not data or not data.get('driver_route_id') or not data.get('incident_type'):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Check if the driver_route belongs to the current driver
    driver_route = DriverRoute.query.filter_by(
        id=data['driver_route_id'], 
        driver_id=current_driver.id
    ).first()
    
    if not driver_route:
        return jsonify({'message': 'Driver route not found'}), 404
    
    # Create incident record
    incident = RouteIncident(
        driver_route_id=driver_route.id,
        driver_id=current_driver.id,
        incident_type=data['incident_type'],
        description=data.get('description', ''),
        location_lat=data.get('location_lat', 0),
        location_lng=data.get('location_lng', 0),
        location_address=data.get('location_address', '')
    )
    
    db.session.add(incident)
    db.session.commit()
    
    # Get pending/incomplete delivery stops
    pending_stops = DeliveryStop.query.filter_by(
        driver_route_id=driver_route.id
    ).filter(
        DeliveryStop.status.in_(['pending', 'arrived'])
    ).all()
    
    # Find nearby drivers who could assist
    if len(pending_stops) > 0:
        # Import calculate_remaining_capacity locally to avoid circular imports
        def calculate_remaining_capacity(stops):
            """Calculate the remaining capacity needed for undelivered stops."""
            return len(stops) * 0.1  # Simple calculation based on stop count
        
            # Define a local find_nearby_drivers function to avoid circular imports
        def local_find_nearby_drivers(lat, lng, exclude_driver_id=None, needed_vehicle_type=None, radius_km=20):
            """Local version to avoid circular imports"""
            # Find active drivers 
            now = datetime.utcnow()
            threshold = now - timedelta(minutes=30)  # Last 30 minutes - fixed to use timedelta
            
            query = Driver.query.filter(
                Driver.is_active == True,
                Driver.last_login > threshold
            )
            
            if exclude_driver_id:
                query = query.filter(Driver.id != exclude_driver_id)
            
            # Filter based on vehicle type if needed
            if needed_vehicle_type:
                query = query.join(Driver.vehicle).filter(
                    Vehicle.vehicle_type == needed_vehicle_type
                )
            
            potential_drivers = query.all()
            
            # Filter by distance (if lat/lng is available)
            nearby_drivers = []
            for driver in potential_drivers:
                if driver.last_known_latitude and driver.last_known_longitude:
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
        # Define a local calculate_distance function to avoid circular imports
        def calculate_distance(lat1, lng1, lat2, lng2):
            """Calculate the great circle distance between two points on earth."""
            import math
            # Convert decimal degrees to radians
            lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
            
            # Haversine formula
            dlat = lat2 - lat1
            dlng = lng2 - lng1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
            c = 2 * math.asin(math.sqrt(a))
            r = 6371  # Radius of earth in kilometers
            
            return c * r
            
        # Find nearby drivers who could assist using our local function
        nearby_drivers = local_find_nearby_drivers(
            lat=incident.location_lat, 
            lng=incident.location_lng,
            exclude_driver_id=current_driver.id,
            needed_vehicle_type=current_driver.vehicle.vehicle_type if current_driver.vehicle else None
        )
        
        # Create route transfer record if nearby drivers are available
        if nearby_drivers:
            # Calculate optimal transfer based on remaining stops
            transfer = RouteTransfer(
                incident_id=incident.id,
                original_driver_id=current_driver.id,
                original_driver_route_id=driver_route.id,
                stop_ids=json.dumps([stop.id for stop in pending_stops]),
                vehicle_type_required=current_driver.vehicle.vehicle_type if current_driver.vehicle else None,
                min_capacity_required=calculate_remaining_capacity(pending_stops)
            )
            
            db.session.add(transfer)
            db.session.commit()
            
            # Notify nearby drivers and admin
            for driver in nearby_drivers:
                send_driver_notification(
                    driver_id=driver.id,
                    notification_type='assistance_needed',
                    data={
                        'incident_id': incident.id,
                        'transfer_id': transfer.id,
                        'stops_count': len(pending_stops),
                        'location': {
                            'lat': incident.location_lat,
                            'lng': incident.location_lng,
                            'address': incident.location_address
                        }
                    }
                )
            
            # Notify admin about the incident
            notify_admin(
                notification_type='incident_reported',
                data=incident.to_dict()
            )
    
    return jsonify({
        'message': 'Incident reported successfully',
        'incident': incident.to_dict(),
        'pending_stops': len(pending_stops)
    }), 201



# Get available assistance requests (for other drivers to see)
@app.route('/api/driver/assistance-requests', methods=['GET'])
@token_required
def get_assistance_requests(current_driver):
    # Find transfer requests that this driver could potentially help with
    transfers = db.session.query(RouteTransfer).join(
        RouteIncident, RouteIncident.id == RouteTransfer.incident_id
    ).filter(
        RouteTransfer.transfer_status == 'pending',
        RouteTransfer.new_driver_id.is_(None)  # Not yet assigned
    ).all()
    
    # Filter based on vehicle compatibility
    compatible_transfers = []
    for transfer in transfers:
        # Skip if this is the driver who needs help
        if transfer.original_driver_id == current_driver.id:
            continue
            
        # Check if this driver has a compatible vehicle
        is_compatible = True
        if current_driver.vehicle and transfer.vehicle_type_required:
            if current_driver.vehicle.vehicle_type != transfer.vehicle_type_required:
                is_compatible = False
                
        if is_compatible:
            # Calculate distance to incident
            incident = transfer.incident
            distance = calculate_distance(
                lat1=current_driver.last_known_latitude,
                lng1=current_driver.last_known_longitude,
                lat2=incident.location_lat,
                lng2=incident.location_lng
            ) if current_driver.last_known_latitude else None
            
            transfer_dict = transfer.to_dict()
            transfer_dict['distance_km'] = distance
            compatible_transfers.append(transfer_dict)
    
    return jsonify(compatible_transfers), 200

# Accept a route transfer
@app.route('/api/driver/transfers/<int:transfer_id>/accept', methods=['POST'])
@token_required
def accept_transfer(current_driver, transfer_id):
    # Find the transfer
    transfer = RouteTransfer.query.get_or_404(transfer_id)
    
    # Check if transfer is still available
    if transfer.transfer_status != 'pending' or transfer.new_driver_id is not None:
        return jsonify({'message': 'This transfer is no longer available'}), 400
    
    # Check if driver has active route
    active_route = DriverRoute.query.filter_by(
        driver_id=current_driver.id,
        status='in_progress'
    ).first()
    
    # Create a new driver route for the transferred stops
    route = Route.query.get(transfer.original_driver_route.route_id)
    
    new_driver_route = DriverRoute(
        driver_id=current_driver.id,
        route_id=route.id,
        status='in_progress',
        started_at=datetime.utcnow(),
        is_transfer=True,
        original_driver_route_id=transfer.original_driver_route_id
    )
    
    db.session.add(new_driver_route)
    db.session.flush()  # Get ID without committing
    
    # Update the transfer
    transfer.new_driver_id = current_driver.id
    transfer.new_driver_route_id = new_driver_route.id
    transfer.transfer_status = 'accepted'
    transfer.transfer_accepted_at = datetime.utcnow()
    
    # Transfer the delivery stops
    stop_ids = transfer.stop_id_list
    for stop_id in stop_ids:
        stop = DeliveryStop.query.get(stop_id)
        if stop:
            # Create a copy of the stop for the new driver
            new_stop = DeliveryStop(
                driver_route_id=new_driver_route.id,
                location_id=stop.location_id,
                stop_number=stop.stop_number,
                planned_arrival_time=stop.planned_arrival_time,
                status='pending',
                original_stop_id=stop.id
            )
            db.session.add(new_stop)
            
            # Update original stop status
            stop.status = 'transferred'
            stop.completion_notes = f"Transferred to driver {current_driver.id} due to incident"
    
    # Update incident status
    incident = transfer.incident
    incident.status = 'assistance_assigned'
    
    db.session.commit()
    
    # Notify the original driver that help is on the way
    send_driver_notification(
        driver_id=transfer.original_driver_id,
        notification_type='assistance_assigned',
        data={
            'helper_driver_name': f"{current_driver.first_name} {current_driver.last_name}",
            'helper_vehicle': current_driver.vehicle.name if current_driver.vehicle else 'Unknown',
            'stops_count': len(stop_ids)
        }
    )
    
    return jsonify({
        'message': 'Transfer accepted successfully',
        'transfer': transfer.to_dict(),
        'new_route_id': new_driver_route.id
    }), 200

# Get pending incident status (for original driver)
@app.route('/api/driver/incidents/active', methods=['GET'])
@token_required
def get_active_incidents(current_driver):
    active_incidents = RouteIncident.query.filter_by(
        driver_id=current_driver.id,
        status='reported'
    ).order_by(RouteIncident.reported_at.desc()).all()
    
    incident_data = []
    for incident in active_incidents:
        data = incident.to_dict()
        
        # Add transfer status information
        transfers = RouteTransfer.query.filter_by(incident_id=incident.id).all()
        transfer_status = 'pending'
        helper_info = None
        
        for transfer in transfers:
            if transfer.transfer_status == 'accepted':
                transfer_status = 'accepted'
                helper_info = {
                    'driver_name': f"{transfer.new_driver.first_name} {transfer.new_driver.last_name}",
                    'vehicle': transfer.new_driver.vehicle.name if transfer.new_driver.vehicle else None,
                    'stops_count': len(transfer.stop_id_list),
                    'accepted_at': transfer.transfer_accepted_at.isoformat() if transfer.transfer_accepted_at else None
                }
                break
        
        data['help_status'] = transfer_status
        data['helper_info'] = helper_info
        incident_data.append(data)
    
    return jsonify(incident_data), 200

# Cancel an incident (if resolved without assistance)
@app.route('/api/driver/incidents/<int:incident_id>/cancel', methods=['POST'])
@token_required
def cancel_incident(current_driver, incident_id):
    incident = RouteIncident.query.get_or_404(incident_id)
    
    # Verify ownership
    if incident.driver_id != current_driver.id:
        return jsonify({'message': 'Unauthorized access to this incident'}), 403
    
    # Cancel all pending transfers
    pending_transfers = RouteTransfer.query.filter_by(
        incident_id=incident.id,
        transfer_status='pending'
    ).all()
    
    for transfer in pending_transfers:
        transfer.transfer_status = 'cancelled'
    
    # Update incident status
    incident.status = 'resolved'
    incident.resolved_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'Incident cancelled successfully',
        'incident': incident.to_dict()
    }), 200

# Utility function to calculate remaining capacity needed
def calculate_remaining_capacity(stops):
    return len(stops) * 0.1  



# Admin endpoint to get all incidents
@app.route('/api/admin/incidents', methods=['GET'])
def admin_get_incidents():
    # Get all incidents, most recent first
    incidents = RouteIncident.query.order_by(RouteIncident.reported_at.desc()).all()
    
    # Get counts for dashboard
    active_count = RouteIncident.query.filter(RouteIncident.status != 'resolved').count()
    pending_transfers = RouteTransfer.query.filter_by(transfer_status='pending').count()
    
    # Get available drivers count (simplified)
    available_drivers = Driver.query.filter_by(is_active=True).count()
    
    return jsonify({
        'incidents': [incident.to_dict() for incident in incidents],
        'counts': {
            'active': active_count,
            'pending_transfers': pending_transfers,
            'available_drivers': available_drivers
        }
    }), 200

# Admin endpoint to get available drivers for an incident
@app.route('/api/admin/incidents/<int:incident_id>/available-drivers', methods=['GET'])
def admin_get_available_drivers(incident_id):
    # Find the incident
    incident = RouteIncident.query.get_or_404(incident_id)
    
    # Find available drivers
    available_drivers = find_nearby_drivers(
        lat=incident.location_lat,
        lng=incident.location_lng,
        exclude_driver_id=incident.driver_id,
        radius_km=50  # Larger radius for admin assignment
    )
    
    # Format driver data
    driver_data = []
    for driver in available_drivers:
        driver_data.append({
            'id': driver.id,
            'name': f"{driver.first_name} {driver.last_name}",
            'vehicle': driver.vehicle.name if driver.vehicle else None,
            'distance_km': getattr(driver, 'distance_km', 0)
        })
    
    return jsonify(driver_data), 200

# Admin endpoint to assign a driver to an incident
@app.route('/api/admin/incidents/<int:incident_id>/assign-driver', methods=['POST'])
def admin_assign_driver(incident_id):
    data = request.get_json()
    
    if not data or not data.get('driver_id'):
        return jsonify({'message': 'Driver ID is required'}), 400
    
    # Find the incident
    incident = RouteIncident.query.get_or_404(incident_id)
    
    # Find pending transfers
    pending_transfer = RouteTransfer.query.filter_by(
        incident_id=incident_id,
        transfer_status='pending'
    ).first()
    
    if not pending_transfer:
        return jsonify({'message': 'No pending transfers found for this incident'}), 404
    
    # Find the driver
    driver = Driver.query.get_or_404(data['driver_id'])
    
    # Create a new driver route for the assigned driver
    original_driver_route = pending_transfer.original_driver_route
    route = Route.query.get(original_driver_route.route_id)
    
    new_driver_route = DriverRoute(
        driver_id=driver.id,
        route_id=route.id,
        status='in_progress',
        started_at=datetime.utcnow(),
        is_transfer=True,
        original_driver_route_id=original_driver_route.id
    )
    
    db.session.add(new_driver_route)
    db.session.flush()  # Get ID without committing
    
    # Update the transfer
    pending_transfer.new_driver_id = driver.id
    pending_transfer.new_driver_route_id = new_driver_route.id
    pending_transfer.transfer_status = 'accepted'
    pending_transfer.transfer_accepted_at = datetime.utcnow()
    
    # Transfer the delivery stops
    stop_ids = pending_transfer.stop_id_list
    for stop_id in stop_ids:
        stop = DeliveryStop.query.get(stop_id)
        if stop:
            # Create a copy of the stop for the new driver
            new_stop = DeliveryStop(
                driver_route_id=new_driver_route.id,
                location_id=stop.location_id,
                stop_number=stop.stop_number,
                planned_arrival_time=stop.planned_arrival_time,
                status='pending',
                original_stop_id=stop.id
            )
            db.session.add(new_stop)
            
            # Update original stop status
            stop.status = 'transferred'
            stop.completion_notes = f"Transferred to driver {driver.id} by admin"
    
    # Update incident status
    incident.status = 'assistance_assigned'
    
    db.session.commit()
    
    # Notify the original driver that help is on the way
    send_driver_notification(
        driver_id=incident.driver_id,
        notification_type='assistance_assigned',
        data={
            'helper_driver_name': f"{driver.first_name} {driver.last_name}",
            'helper_vehicle': driver.vehicle.name if driver.vehicle else 'Unknown',
            'stops_count': len(stop_ids)
        }
    )
    
    # Notify the assigned driver
    send_driver_notification(
        driver_id=driver.id,
        notification_type='assignment_received',
        data={
            'incident_id': incident.id,
            'transfer_id': pending_transfer.id,
            'stops_count': len(stop_ids),
            'location': {
                'lat': incident.location_lat,
                'lng': incident.location_lng,
                'address': incident.location_address
            }
        }
    )
    
    return jsonify({
        'message': 'Driver assigned successfully',
        'transfer': pending_transfer.to_dict()
    }), 200

# Admin endpoint to resolve an incident
@app.route('/api/admin/incidents/<int:incident_id>/resolve', methods=['POST'])
def admin_resolve_incident(incident_id):
    # Find the incident
    incident = RouteIncident.query.get_or_404(incident_id)
    
    # Update incident status
    incident.status = 'resolved'
    incident.resolved_at = datetime.utcnow()
    
    # Cancel any pending transfers
    pending_transfers = RouteTransfer.query.filter_by(
        incident_id=incident_id,
        transfer_status='pending'
    ).all()
    
    for transfer in pending_transfers:
        transfer.transfer_status = 'cancelled'
    
    db.session.commit()
    
    return jsonify({
        'message': 'Incident resolved successfully',
        'incident': incident.to_dict()
    }), 200

# Admin incidents dashboard route
@app.route('/admin/incidents')
def admin_incidents_dashboard():
    return render_template('admin_incidents.html')


# Get notifications endpoint (for both drivers and admins)
@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    # Get user type and ID from token or session (simplified)
    user_type = request.args.get('user_type', 'admin')
    user_id = request.args.get('user_id', 1)  # Default to admin ID 1
    
    # Check for token (for drivers)
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            user_type = 'driver'
            user_id = data.get('id')
        except:
            pass
    
    # Get notifications for this user
    notifications = Notification.query.filter_by(
        recipient_type=user_type,
        recipient_id=user_id
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    # Count unread notifications
    unread_count = Notification.query.filter_by(
        recipient_type=user_type,
        recipient_id=user_id,
        is_read=False
    ).count()
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications],
        'unread_count': unread_count
    }), 200

# Mark notification as read
@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_as_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    # In a real system, verify the notification belongs to the current user
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Notification marked as read',
        'notification': notification.to_dict()
    }), 200

# Mark all notifications as read
@app.route('/api/notifications/read-all', methods=['POST'])
def mark_all_notifications_as_read():
    # Get user type and ID (simplified)
    user_type = request.args.get('user_type', 'admin')
    user_id = request.args.get('user_id', 1)  # Default to admin ID 1
    
    # Check for token (for drivers)
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            user_type = 'driver'
            user_id = data.get('id')
        except:
            pass
    
    # Mark all notifications as read
    notifications = Notification.query.filter_by(
        recipient_type=user_type,
        recipient_id=user_id,
        is_read=False
    ).all()
    
    for notification in notifications:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'message': 'All notifications marked as read',
        'count': len(notifications)
    }), 200


@app.route('/api/driver/update-location', methods=['POST'])
@token_required
def update_driver_location(current_driver):
    data = request.get_json()
    
    if not data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({'message': 'Latitude and longitude are required'}), 400
    
    # Update driver location
    current_driver.last_known_latitude = data['latitude']
    current_driver.last_known_longitude = data['longitude']
    db.session.commit()
    
    return jsonify({
        'message': 'Location updated successfully',
        'location': {
            'latitude': current_driver.last_known_latitude,
            'longitude': current_driver.last_known_longitude
        }
    }), 200



if __name__ == '__main__':
    # Create database if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
    
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)