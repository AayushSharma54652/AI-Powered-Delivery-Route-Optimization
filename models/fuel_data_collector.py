import pandas as pd
import numpy as np
import json
import logging
import os
from datetime import datetime, timedelta
import joblib
from sqlalchemy import text

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FuelDataCollector:
    """
    Collects and processes actual fuel consumption data to improve prediction models.
    """
    def __init__(self, db, model_path=None):
        """
        Initialize the fuel data collector.
        
        Args:
            db: SQLAlchemy database instance
            model_path (str, optional): Path to saved fuel prediction model
        """
        self.db = db
        self.model_path = model_path or 'models/fuel_consumption_model.pkl'
        self.training_data_path = 'data/fuel_training_data.csv'
    
    def _execute_query(self, query_str, params=None):
        """
        Execute SQL query with proper connection handling.
        
        Args:
            query_str (str): SQL query to execute
            params (dict, optional): Parameters for the query
            
        Returns:
            list: Query results
        """
        try:
            # Use SQLAlchemy text() function
            sql_query = text(query_str)
            
            # Try using SQLAlchemy session directly
            try:
                result = self.db.session.execute(sql_query, params or {})
                return result.fetchall()
            except Exception as e1:
                logger.error(f"Session query failed: {e1}")
                # Try using engine connect
                try:
                    with self.db.engine.connect() as conn:
                        result = conn.execute(sql_query, params or {})
                        return result.fetchall()
                except Exception as e2:
                    logger.error(f"Engine connect query failed: {e2}")
                    return []
        except Exception as e:
            logger.error(f"Query preparation failed: {e}")
            return []
    
    def record_actual_fuel_consumption(self, route_id, vehicle_id, actual_fuel, 
                                       route_metadata=None, driver_id=None):
        """
        Record actual fuel consumption for a completed route.
        
        Args:
            route_id (int): ID of the completed route
            vehicle_id (int): ID of the vehicle used
            actual_fuel (float): Actual fuel consumption in liters
            route_metadata (dict, optional): Additional route information
            driver_id (int, optional): ID of the driver who completed the route
            
        Returns:
            bool: Success status
        """
        try:
            # Import here to avoid circular imports
            from models.fuel_consumption_model import FuelConsumptionPredictor
            
            # Get route, vehicle, and driver using direct queries
            route = self.db.session.get(self.db.Model.registry._class_registry['Route'], route_id)
            vehicle = self.db.session.get(self.db.Model.registry._class_registry['Vehicle'], vehicle_id)
            driver = self.db.session.get(self.db.Model.registry._class_registry['Driver'], driver_id) if driver_id else None
            
            if not route or not vehicle:
                logger.error(f"Route {route_id} or Vehicle {vehicle_id} not found.")
                return False
            
            # Get route data from JSON
            route_data = json.loads(route.route_data)
            
            # Find the specific vehicle's route
            vehicle_route = None
            for vr in route_data:
                if vr.get('vehicle_id') == vehicle_id:
                    vehicle_route = vr
                    break
            
            # If no specific vehicle route found, use the first one
            if not vehicle_route and route_data:
                vehicle_route = route_data[0]
            
            if not vehicle_route:
                logger.error(f"No route data found for route {route_id}.")
                return False
            
            # Create a record of actual fuel consumption
            new_record = {
                'route_id': route_id,
                'vehicle_id': vehicle_id,
                'driver_id': driver_id,
                'predicted_fuel': vehicle_route.get('total_fuel', 0),
                'actual_fuel': actual_fuel,
                'prediction_error': actual_fuel - vehicle_route.get('total_fuel', 0),
                'distance': vehicle_route.get('total_distance', 0),
                'vehicle_type': vehicle.vehicle_type if vehicle else vehicle_route.get('vehicle_type', 'van'),
                'vehicle_weight': vehicle.weight if vehicle else 0,
                'load_weight': route_metadata.get('load_weight', 0) if route_metadata else 0,
                'avg_speed': route_metadata.get('avg_speed', 30) if route_metadata else 30,
                'traffic_factor': route_metadata.get('traffic_factor', 1.0) if route_metadata else 1.0,
                'stop_frequency': len(vehicle_route.get('stops', [])) / vehicle_route.get('total_distance', 1),
                'road_type': route_metadata.get('road_type', 'mixed') if route_metadata else 'mixed',
                'gradient': route_metadata.get('gradient', 0) if route_metadata else 0,
                'temperature': route_metadata.get('temperature', 25) if route_metadata else 25,
                'date_recorded': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'driver_efficiency_rating': route_metadata.get('driver_efficiency', 1.0) if route_metadata else 1.0
            }
            
            # Get existing fuel data records or create new DataFrame
            df = self._load_training_data()
            
            # Add new record
            df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
            
            # Save to CSV
            self._save_training_data(df)
            
            # Update route with actual fuel consumption
            route.actual_fuel = actual_fuel
            route.fuel_accuracy = (vehicle_route.get('total_fuel', 0) / actual_fuel) if actual_fuel > 0 else 0
            
            # Add driver efficiency rating if driver exists
            if driver:
                self._update_driver_efficiency(driver, new_record)
            
            # Commit changes to database
            self.db.session.commit()
            
            logger.info(f"Recorded actual fuel consumption for route {route_id}: {actual_fuel} liters")
            return True
            
        except Exception as e:
            logger.error(f"Error recording actual fuel consumption: {e}")
            return False
    
    def retrain_model(self, force=False):
        """
        Retrain the fuel consumption prediction model with collected data.
        
        Args:
            force (bool): Force retraining even if minimal data
            
        Returns:
            bool: Success status
        """
        try:
            # Import here to avoid circular imports
            from models.fuel_consumption_model import FuelConsumptionPredictor
            
            # Load training data
            df = self._load_training_data()
            
            # Check if we have enough data
            if len(df) < 10 and not force:
                logger.info("Not enough training data (minimum 10 records). Skipping retraining.")
                return False
            
            # Initialize model
            predictor = FuelConsumptionPredictor(self.model_path)
            
            # Train the model
            predictor.train(df)
            
            logger.info(f"Successfully retrained fuel consumption model with {len(df)} records")
            return True
            
        except Exception as e:
            logger.error(f"Error retraining fuel consumption model: {e}")
            return False
    
    # Updated analyze_prediction_accuracy method to not return sample data
    def analyze_prediction_accuracy(self):
        """
        Analyze the accuracy of fuel consumption predictions.
        
        Returns:
            dict: Accuracy metrics or empty data if no records are found
        """
        try:
            # Load training data
            df = self._load_training_data()
            
            if len(df) < 1:
                return {
                    'record_count': 0,
                    'mean_absolute_error': None,
                    'mean_error_percent': None,
                    'accuracy': None,
                    'overestimation_rate': None,
                    'underestimation_rate': None,
                    'by_vehicle_type': {},
                    'by_road_type': {},
                    'recent_trend': {
                        'count': 0,
                        'accuracy': None
                    },
                    'no_data': True  # Flag to indicate no data
                }
            
            # Check if prediction_error column exists
            if 'prediction_error' not in df.columns:
                # Create it if it doesn't
                df['prediction_error'] = df['actual_fuel'] - df['predicted_fuel']
            
            # Check if error_percent column exists
            if 'error_percent' not in df.columns:
                # Create it and handle divide by zero
                df['error_percent'] = np.where(
                    df['actual_fuel'] > 0,
                    (df['prediction_error'] / df['actual_fuel']) * 100,
                    0
                )
            
            metrics = {
                'record_count': len(df),
                'mean_absolute_error': float(df['prediction_error'].abs().mean()),
                'mean_error_percent': float(df['error_percent'].abs().mean()),
                'accuracy': float(100 - df['error_percent'].abs().mean()),
                'overestimation_rate': float((df['prediction_error'] > 0).mean() * 100),
                'underestimation_rate': float((df['prediction_error'] < 0).mean() * 100),
                'by_vehicle_type': {},
                'by_road_type': {},
                'recent_trend': {},
                'no_data': False
            }
            
            # Calculate metrics by vehicle type
            for vehicle_type in df['vehicle_type'].unique():
                type_df = df[df['vehicle_type'] == vehicle_type]
                metrics['by_vehicle_type'][vehicle_type] = {
                    'count': int(len(type_df)),
                    'accuracy': float(100 - type_df['error_percent'].abs().mean())
                }
            
            # Calculate metrics by road type
            for road_type in df['road_type'].unique():
                type_df = df[df['road_type'] == road_type]
                metrics['by_road_type'][road_type] = {
                    'count': int(len(type_df)),
                    'accuracy': float(100 - type_df['error_percent'].abs().mean())
                }
            
            # Calculate recent trend (last 10 records)
            if 'date_recorded' in df.columns:
                recent_df = df.sort_values('date_recorded', ascending=False).head(10)
                metrics['recent_trend'] = {
                    'count': int(len(recent_df)),
                    'accuracy': float(100 - recent_df['error_percent'].abs().mean() if len(recent_df) > 0 else None)
                }
            else:
                metrics['recent_trend'] = {
                    'count': 0,
                    'accuracy': None
                }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing prediction accuracy: {e}")
            # Return empty metrics on error instead of sample data
            return {
                'record_count': 0,
                'mean_absolute_error': None,
                'mean_error_percent': None,
                'accuracy': None,
                'overestimation_rate': None,
                'underestimation_rate': None,
                'by_vehicle_type': {},
                'by_road_type': {},
                'recent_trend': {
                    'count': 0,
                    'accuracy': None
                },
                'no_data': True,
                'error': str(e)
            }


    def get_driver_efficiency_ranking(self):
        """
        Get efficiency ranking of drivers based on actual vs predicted fuel consumption.
        
        Returns:
            list: Ranked list of driver efficiency or empty list if no data
        """
        try:
            # Instead of directly importing Driver model, use the db instance that's passed in
            Driver = self.db.Model.registry._class_registry.get('Driver')
            
            if not Driver:
                logger.error("Driver model not found in registry")
                return []
                
            drivers = Driver.query.all()
            
            if not drivers:
                # Return empty list instead of sample data
                return []
            
            # Check if we have any actual data in the training dataset
            df = self._load_training_data()
            
            if len(df) < 1:
                # No training data, so we can't calculate real efficiency
                return []
            
            # Get actual data for drivers with recorded trips
            driver_data = {}
            for driver in drivers:
                driver_df = df[df['driver_id'] == driver.id]
                
                if len(driver_df) > 0:
                    # Calculate actual efficiency from data
                    efficiency = driver_df['actual_fuel'].sum() / driver_df['predicted_fuel'].sum() if driver_df['predicted_fuel'].sum() > 0 else None
                    fuel_saved = (driver_df['predicted_fuel'] - driver_df['actual_fuel']).sum()
                    fuel_saved = max(0, fuel_saved)  # Only count positive savings
                    
                    driver_data[driver.id] = {
                        'id': driver.id,
                        'name': f"{driver.first_name} {driver.last_name}",
                        'efficiency_rating': efficiency if efficiency is not None else driver.fuel_efficiency_rating,
                        'fuel_saved': fuel_saved if not np.isnan(fuel_saved) else driver.fuel_saved,
                        'routes_completed': len(driver_df)
                    }
                elif driver.fuel_efficiency_rating and driver.routes_completed:
                    # Use stored efficiency if available
                    driver_data[driver.id] = {
                        'id': driver.id,
                        'name': f"{driver.first_name} {driver.last_name}",
                        'efficiency_rating': driver.fuel_efficiency_rating,
                        'fuel_saved': driver.fuel_saved if driver.fuel_saved else 0,
                        'routes_completed': driver.routes_completed if driver.routes_completed else 0
                    }
            
            # Convert to list and filter out None values
            ranking = [data for data in driver_data.values() if data['efficiency_rating'] is not None]
            
            # Sort by efficiency rating (lower is better)
            ranking.sort(key=lambda x: x['efficiency_rating'])
            
            # Return real data only
            return ranking
            
        except Exception as e:
            logger.error(f"Error in get_driver_efficiency_ranking: {e}")
            # Return empty list instead of sample data
            return []
    
    def _load_training_data(self):
        """Load training data from CSV or create empty DataFrame."""
        try:
            if os.path.exists(self.training_data_path):
                return pd.read_csv(self.training_data_path)
            else:
                # Create empty DataFrame with required columns
                columns = [
                    'route_id', 'vehicle_id', 'driver_id', 
                    'predicted_fuel', 'actual_fuel', 'prediction_error',
                    'distance', 'vehicle_type', 'vehicle_weight', 'load_weight',
                    'avg_speed', 'traffic_factor', 'stop_frequency',
                    'road_type', 'gradient', 'temperature',
                    'date_recorded', 'driver_efficiency_rating'
                ]
                return pd.DataFrame(columns=columns)
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return pd.DataFrame()
    
    def _save_training_data(self, df):
        """Save training data to CSV."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.training_data_path), exist_ok=True)
            
            # Save to CSV
            df.to_csv(self.training_data_path, index=False)
            
        except Exception as e:
            logger.error(f"Error saving training data: {e}")
    
    def _update_driver_efficiency(self, driver, record):
        """Update driver's fuel efficiency rating."""
        try:
            # Calculate efficiency rating (ratio of actual to predicted fuel)
            efficiency = record['actual_fuel'] / record['predicted_fuel'] if record['predicted_fuel'] > 0 else 1.0
            
            # Apply smoothing with existing rating if it exists
            if driver.fuel_efficiency_rating:
                # Weight: 30% new data, 70% historical
                driver.fuel_efficiency_rating = 0.3 * efficiency + 0.7 * driver.fuel_efficiency_rating
                driver.routes_completed = driver.routes_completed + 1 if driver.routes_completed else 1
            else:
                # First rating
                driver.fuel_efficiency_rating = efficiency
                driver.routes_completed = 1
            
            # Calculate fuel saved
            predicted_baseline = record['predicted_fuel'] * 1.0  # Standard consumption
            actual_fuel = record['actual_fuel']
            fuel_saved = predicted_baseline - actual_fuel if actual_fuel < predicted_baseline else 0
            
            # Update total fuel saved
            driver.fuel_saved = driver.fuel_saved + fuel_saved if driver.fuel_saved else fuel_saved
            
        except Exception as e:
            logger.error(f"Error updating driver efficiency: {e}")