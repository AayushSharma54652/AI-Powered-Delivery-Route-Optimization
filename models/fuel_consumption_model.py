import numpy as np
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
import joblib
import os
import pandas as pd
import math
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FuelConsumptionPredictor:
    """
    A machine learning model to predict fuel consumption for delivery routes.
    """
    def __init__(self, model_path=None):
        """
        Initialize the fuel consumption prediction model.
        
        Args:
            model_path (str, optional): Path to saved model file
        """
        self.model = None
        self.model_path = model_path or 'models/fuel_consumption_model.pkl'
        
        # Try to load existing model
        try:
            if os.path.exists(self.model_path):
                logger.info(f"Loading existing fuel consumption model from {self.model_path}")
                self.model = joblib.load(self.model_path)
        except Exception as e:
            logger.warning(f"Error loading model: {e}")
            self.model = None
    
    def train(self, training_data):
        """
        Train the fuel consumption prediction model.
        
        Args:
            training_data (DataFrame): DataFrame with features and target
                Required columns:
                - 'distance': Distance in km
                - 'vehicle_type': Type of vehicle (car, van, truck)
                - 'vehicle_weight': Vehicle weight in kg
                - 'load_weight': Cargo weight in kg
                - 'avg_speed': Average speed in km/h
                - 'traffic_factor': Traffic congestion factor (1.0 = no traffic)
                - 'stop_frequency': Number of stops per km
                - 'road_type': Type of road (highway, urban, mixed)
                - 'gradient': Average road gradient (%)
                - 'temperature': Ambient temperature (°C)
                - 'fuel_consumption': Target variable (liters)
        
        Returns:
            self: The trained model instance
        """
        if training_data is None or len(training_data) < 10:
            logger.warning("Insufficient training data, falling back to baseline model")
            self.model = None
            return self
            
        try:
            # Extract features and target
            X = training_data.drop('fuel_consumption', axis=1)
            y = training_data['fuel_consumption']
            
            # Convert categorical features to dummy variables
            X = pd.get_dummies(X, columns=['vehicle_type', 'road_type'], drop_first=True)
            
            # Train model - Gradient Boosting typically works well for this type of prediction
            logger.info("Training fuel consumption model with Gradient Boosting")
            self.model = GradientBoostingRegressor(
                n_estimators=100, 
                learning_rate=0.1, 
                max_depth=5,
                random_state=42
            )
            self.model.fit(X, y)
            
            # Save the model
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            logger.info(f"Fuel consumption model saved to {self.model_path}")
            
            return self
        
        except Exception as e:
            logger.error(f"Error training fuel consumption model: {e}")
            self.model = None
            return self
    
    def predict(self, route_data):
        """
        Predict fuel consumption for a route.
        
        Args:
            route_data (dict or DataFrame): Route information with the same features used for training
                
        Returns:
            float: Predicted fuel consumption in liters
        """
        # Convert dict to DataFrame if needed
        if isinstance(route_data, dict):
            route_data = pd.DataFrame([route_data])
        
        # If no model is available, use baseline calculation
        if self.model is None:
            return self._baseline_prediction(route_data)
        
        try:
            # Preprocess the data
            X = pd.get_dummies(route_data, columns=['vehicle_type', 'road_type'], drop_first=True)
            
            # Add missing columns that might be in the training data but not in the input
            for col in self.model.feature_names_in_:
                if col not in X.columns:
                    X[col] = 0
            
            # Select only the columns the model was trained on
            X = X[self.model.feature_names_in_]
            
            # Make prediction
            prediction = self.model.predict(X)
            return prediction[0] if len(prediction) == 1 else prediction
        
        except Exception as e:
            logger.error(f"Error predicting fuel consumption: {e}")
            return self._baseline_prediction(route_data)
    
    def _baseline_prediction(self, route_data):
        """
        Basic physics-based model for fuel consumption when ML model is not available.
        
        Args:
            route_data (DataFrame): Route information
                
        Returns:
            float: Estimated fuel consumption in liters
        """
        # Extract data from the first row if it's a DataFrame
        if isinstance(route_data, pd.DataFrame):
            data = route_data.iloc[0]
        else:
            data = route_data
        
        # Default values if not provided
        distance = data.get('distance', 0)
        vehicle_type = data.get('vehicle_type', 'van')
        load_weight = data.get('load_weight', 0)
        traffic_factor = data.get('traffic_factor', 1.0)
        stop_frequency = data.get('stop_frequency', 0.1)
        road_type = data.get('road_type', 'mixed')
        
        # Baseline fuel efficiency in L/100km based on vehicle type (empty vehicle)
        base_consumption = {
            'car': 7.0,
            'van': 10.0,
            'truck': 20.0,
            'motorbike': 4.0
        }.get(vehicle_type.lower(), 10.0)
        
        # Adjust for load weight (each 100kg increases consumption by ~1%)
        weight_factor = 1.0 + (load_weight / 1000) * 0.1
        
        # Adjust for traffic (traffic increases consumption significantly)
        # Traffic factor of 2.0 would mean double the fuel consumption
        traffic_adjustment = 0.5 + (traffic_factor * 0.5)
        
        # Adjust for stops (each stop per km increases consumption)
        stop_adjustment = 1.0 + (stop_frequency * 0.5)
        
        # Adjust for road type
        road_adjustment = {
            'highway': 0.8,  # Highways are more efficient
            'urban': 1.3,    # Urban driving is less efficient
            'mixed': 1.0     # Mixed is baseline
        }.get(road_type.lower(), 1.0)
        
        # Calculate fuel consumption in liters
        fuel_consumption = (base_consumption / 100) * distance * weight_factor * traffic_adjustment * stop_adjustment * road_adjustment
        
        return max(0.1, fuel_consumption)  # Ensure positive consumption
    
    def generate_synthetic_training_data(self, num_samples=1000):
        """
        Generate synthetic training data for the fuel consumption model.
        
        Args:
            num_samples (int): Number of samples to generate
            
        Returns:
            DataFrame: Synthetic training data
        """
        np.random.seed(42)
        
        # Generate random features
        data = {
            'distance': np.random.uniform(5, 200, num_samples),  # 5-200 km
            'vehicle_type': np.random.choice(['car', 'van', 'truck'], num_samples),
            'vehicle_weight': np.random.uniform(1000, 10000, num_samples),  # 1-10 tons
            'load_weight': np.random.uniform(0, 5000, num_samples),  # 0-5 tons
            'avg_speed': np.random.uniform(20, 100, num_samples),  # 20-100 km/h
            'traffic_factor': np.random.uniform(1.0, 3.0, num_samples),  # 1-3x traffic
            'stop_frequency': np.random.uniform(0, 1, num_samples),  # 0-1 stops per km
            'road_type': np.random.choice(['highway', 'urban', 'mixed'], num_samples),
            'gradient': np.random.uniform(-5, 5, num_samples),  # -5% to +5%
            'temperature': np.random.uniform(-10, 40, num_samples)  # -10°C to 40°C
        }
        
        df = pd.DataFrame(data)
        
        # Calculate synthetic fuel consumption with some randomness
        # This is a simplified physics-inspired model
        base_consumption = {
            'car': 7.0,
            'van': 10.0,
            'truck': 20.0
        }
        
        fuel_consumption = []
        for _, row in df.iterrows():
            # Base consumption in L/100km
            base = base_consumption[row['vehicle_type']]
            
            # Adjustments
            weight_factor = 1.0 + ((row['vehicle_weight'] + row['load_weight']) / 10000) * 0.2
            speed_factor = 1.0 + abs(row['avg_speed'] - 60) / 60  # Optimal speed around 60 km/h
            traffic_factor = 0.8 + (row['traffic_factor'] * 0.2)
            stop_factor = 1.0 + (row['stop_frequency'] * 0.3)
            road_factor = 1.2 if row['road_type'] == 'urban' else (0.9 if row['road_type'] == 'highway' else 1.0)
            gradient_factor = 1.0 + (abs(row['gradient']) * 0.05)
            temp_factor = 1.0 + (abs(row['temperature'] - 20) / 100)  # Optimal temp around 20°C
            
            # Calculate consumption in liters
            consumption = (base / 100) * row['distance'] * weight_factor * speed_factor * traffic_factor * stop_factor * road_factor * gradient_factor * temp_factor
            
            # Add some random noise (±10%)
            noise = np.random.uniform(0.9, 1.1)
            fuel_consumption.append(consumption * noise)
        
        df['fuel_consumption'] = fuel_consumption
        
        return df