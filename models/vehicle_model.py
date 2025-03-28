"""
Vehicle data with fuel efficiency information for different vehicle types.
"""

# Default fuel efficiency data (liters/100km)
DEFAULT_FUEL_EFFICIENCY = {
    'car': {
        'base_consumption': 7.0,  # L/100km
        'weight': 1500,           # kg
        'max_load': 400,          # kg
        'capacity': 2,            # cubic meters
    },
    'van': {
        'base_consumption': 10.0,  # L/100km
        'weight': 2500,            # kg
        'max_load': 1200,          # kg
        'capacity': 8,             # cubic meters
    },
    'truck': {
        'base_consumption': 20.0,  # L/100km
        'weight': 7500,            # kg
        'max_load': 5000,          # kg
        'capacity': 30,            # cubic meters
    },
    'motorbike': {
        'base_consumption': 4.0,   # L/100km
        'weight': 200,             # kg
        'max_load': 50,            # kg
        'capacity': 0.2,           # cubic meters
    }
}

def get_vehicle_efficiency_data(vehicle_type=None, vehicle_id=None, db=None):
    """
    Get fuel efficiency data for a specific vehicle.
    
    Args:
        vehicle_type (str, optional): Type of vehicle (car, van, truck, etc.)
        vehicle_id (int, optional): Database ID of the vehicle
        db (SQLAlchemy.db, optional): Database connection to query vehicle data
        
    Returns:
        dict: Vehicle fuel efficiency data
    """
    # If we have a database and vehicle ID, try to get actual vehicle data
    if db and vehicle_id:
        try:
            from models import Vehicle
            vehicle = Vehicle.query.get(vehicle_id)
            if vehicle:
                # Use the actual vehicle data with default efficiency as fallback
                vehicle_type = vehicle.vehicle_type.lower()
                default_data = DEFAULT_FUEL_EFFICIENCY.get(vehicle_type, DEFAULT_FUEL_EFFICIENCY['van'])
                
                return {
                    'type': vehicle_type,
                    'name': vehicle.name,
                    'license_plate': vehicle.license_plate,
                    'weight': vehicle.weight if hasattr(vehicle, 'weight') else default_data['weight'],
                    'max_load': vehicle.max_weight,
                    'capacity': vehicle.capacity,
                    'base_consumption': getattr(vehicle, 'fuel_consumption', default_data['base_consumption'])
                }
        except Exception as e:
            print(f"Error getting vehicle data: {e}")
    
    # Fallback to defaults based on vehicle type
    if vehicle_type and vehicle_type.lower() in DEFAULT_FUEL_EFFICIENCY:
        data = DEFAULT_FUEL_EFFICIENCY[vehicle_type.lower()]
        return {
            'type': vehicle_type.lower(),
            'weight': data['weight'],
            'max_load': data['max_load'],
            'capacity': data['capacity'],
            'base_consumption': data['base_consumption']
        }
    
    # Default to van if no matching type
    data = DEFAULT_FUEL_EFFICIENCY['van']
    return {
        'type': 'van',
        'weight': data['weight'],
        'max_load': data['max_load'],
        'capacity': data['capacity'],
        'base_consumption': data['base_consumption']
    }

def calculate_co2_emissions(fuel_consumption, fuel_type='diesel'):
    """
    Calculate CO2 emissions based on fuel consumption.
    
    Args:
        fuel_consumption (float): Fuel consumption in liters
        fuel_type (str): Type of fuel (diesel, petrol, etc.)
        
    Returns:
        float: CO2 emissions in kg
    """
    # CO2 emission factors (kg CO2 per liter of fuel)
    emission_factors = {
        'diesel': 2.68,
        'petrol': 2.31,
        'gasoline': 2.31,  # Same as petrol
        'lpg': 1.51,
        'cng': 1.63,  # Compressed Natural Gas
    }
    
    factor = emission_factors.get(fuel_type.lower(), 2.68)  # Default to diesel
    return fuel_consumption * factor