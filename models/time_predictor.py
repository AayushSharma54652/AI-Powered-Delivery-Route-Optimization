import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
import datetime
import pickle
import os
from pathlib import Path

class TravelTimePredictor:
    def __init__(self, model_path=None):
        """
        Initialize the travel time prediction model.
        
        Args:
            model_path (str, optional): Path to saved model file
        """
        self.model = None
        self.model_path = model_path or 'models/time_prediction_model.pkl'
        
        # Try to load existing model
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
        except Exception as e:
            print(f"Error loading model: {e}")
    
    def train(self, distance_data, time_data, time_of_day=None, day_of_week=None):
        """
        Train the time prediction model.
        
        Args:
            distance_data (list): List of distances
            time_data (list): List of corresponding travel times
            time_of_day (list, optional): List of times of day
            day_of_week (list, optional): List of days of week
        """
        # Prepare features
        features = np.array(distance_data).reshape(-1, 1)
        
        # Add time of day and day of week if provided
        if time_of_day is not None:
            # Convert time string to hour of day (float)
            hour_data = [float(t.split(':')[0]) + float(t.split(':')[1])/60 
                         if isinstance(t, str) else 12.0 for t in time_of_day]
            # Create sin and cos features to represent cyclical nature of time
            hour_sin = np.sin(2 * np.pi * np.array(hour_data) / 24)
            hour_cos = np.cos(2 * np.pi * np.array(hour_data) / 24)
            features = np.column_stack((features, hour_sin.reshape(-1, 1), hour_cos.reshape(-1, 1)))
        
        if day_of_week is not None:
            # Convert day to numeric (0=Monday, 6=Sunday)
            day_data = []
            for d in day_of_week:
                if isinstance(d, int) and 0 <= d <= 6:
                    day_data.append(d)
                elif isinstance(d, str):
                    try:
                        day_data.append({"monday": 0, "tuesday": 1, "wednesday": 2, 
                                        "thursday": 3, "friday": 4, "saturday": 5, 
                                        "sunday": 6}[d.lower()])
                    except KeyError:
                        day_data.append(0)  # Default to Monday
                else:
                    day_data.append(0)  # Default to Monday
            
            # Create sin and cos features for days of week
            day_sin = np.sin(2 * np.pi * np.array(day_data) / 7)
            day_cos = np.cos(2 * np.pi * np.array(day_data) / 7)
            features = np.column_stack((features, day_sin.reshape(-1, 1), day_cos.reshape(-1, 1)))
        
        # Check if we have enough data
        if len(time_data) < 10:
            # Not enough data, use simple linear model
            self.model = LinearRegression()
        else:
            # More data, use random forest
            self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        
        # Train the model
        self.model.fit(features, time_data)
        
        # Save the model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump(self.model, f)
    
    def predict(self, distances, time_of_day=None, day_of_week=None):
        """
        Predict travel times based on distances.
        
        Args:
            distances (list): List of distances to predict time for
            time_of_day (list, optional): List of times of day
            day_of_week (list, optional): List of days of week
            
        Returns:
            list: Predicted travel times
        """
        if self.model is None:
            # If no model is trained, estimate based on average speed of 30 km/h
            return [d / 30 for d in distances]
        
        # Prepare features
        features = np.array(distances).reshape(-1, 1)
        
        # Add time of day if provided
        if time_of_day is not None:
            # Convert time string to hour of day (float)
            hour_data = []
            for t in time_of_day:
                if isinstance(t, str):
                    parts = t.split(':')
                    hour_data.append(float(parts[0]) + float(parts[1])/60)
                elif isinstance(t, datetime.time):
                    hour_data.append(t.hour + t.minute/60)
                else:
                    hour_data.append(12.0)  # Default to noon
            
            # Create sin and cos features
            hour_sin = np.sin(2 * np.pi * np.array(hour_data) / 24)
            hour_cos = np.cos(2 * np.pi * np.array(hour_data) / 24)
            features = np.column_stack((features, hour_sin.reshape(-1, 1), hour_cos.reshape(-1, 1)))
        
        # Add day of week if provided
        if day_of_week is not None:
            # Convert day to numeric (0=Monday, 6=Sunday)
            day_data = []
            for d in day_of_week:
                if isinstance(d, int) and 0 <= d <= 6:
                    day_data.append(d)
                elif isinstance(d, str):
                    try:
                        day_data.append({"monday": 0, "tuesday": 1, "wednesday": 2, 
                                         "thursday": 3, "friday": 4, "saturday": 5, 
                                         "sunday": 6}[d.lower()])
                    except KeyError:
                        day_data.append(0)  # Default to Monday
                elif isinstance(d, datetime.date):
                    day_data.append(d.weekday())
                else:
                    day_data.append(0)  # Default to Monday
            
            # Create sin and cos features
            day_sin = np.sin(2 * np.pi * np.array(day_data) / 7)
            day_cos = np.cos(2 * np.pi * np.array(day_data) / 7)
            features = np.column_stack((features, day_sin.reshape(-1, 1), day_cos.reshape(-1, 1)))
        
        # Predict travel times
        predicted_times = self.model.predict(features)
        
        # Ensure predictions are reasonable (at least 5 min for any distance)
        return [max(p, d / 60) for p, d in zip(predicted_times, distances)]


def predict_travel_time(distance_matrix, time_of_day=None, day_of_week=None):
    """
    Predict travel times for a distance matrix.
    
    Args:
        distance_matrix (list): 2D matrix of distances
        time_of_day (str or list, optional): Time of day
        day_of_week (str or list, optional): Day of week
        
    Returns:
        list: 2D matrix of predicted travel times
    """
    predictor = TravelTimePredictor()
    
    # Flatten distance matrix for prediction
    distances = []
    indices = []
    for i in range(len(distance_matrix)):
        for j in range(len(distance_matrix[i])):
            if i != j:  # Skip self-distances
                distances.append(distance_matrix[i][j])
                indices.append((i, j))
    
    # Prepare time and day inputs
    times = None
    days = None
    
    if time_of_day is not None:
        if isinstance(time_of_day, (str, datetime.time)):
            times = [time_of_day] * len(distances)
        else:
            # Expand time_of_day to match distance matrix
            times = []
            for i, j in indices:
                if isinstance(time_of_day, list) and len(time_of_day) > i:
                    times.append(time_of_day[i])
                else:
                    times.append(datetime.datetime.now().strftime("%H:%M"))
    
    if day_of_week is not None:
        if isinstance(day_of_week, (str, int, datetime.date)):
            days = [day_of_week] * len(distances)
        else:
            # Expand day_of_week to match distance matrix
            days = []
            for i, j in indices:
                if isinstance(day_of_week, list) and len(day_of_week) > i:
                    days.append(day_of_week[i])
                else:
                    days.append(datetime.datetime.now().weekday())
    
    # Predict travel times
    predicted_times = predictor.predict(distances, times, days)
    
    # Reconstruct time matrix
    time_matrix = [[0 for _ in range(len(distance_matrix))] for _ in range(len(distance_matrix))]
    for k, (i, j) in enumerate(indices):
        time_matrix[i][j] = predicted_times[k]
    
    # Fill diagonal with zeros
    for i in range(len(time_matrix)):
        time_matrix[i][i] = 0
    
    return time_matrix