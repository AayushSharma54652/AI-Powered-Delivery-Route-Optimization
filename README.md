# AI-Powered Delivery Route Optimization System

## Overview

This AI-Powered Delivery Route Optimization System is an advanced solution designed to help delivery businesses minimize transportation costs, reduce fuel consumption, and optimize route planning using state-of-the-art machine learning and optimization algorithms.

## 🚀 Key Features

### Route Optimization
- Multi-stop routing with time window constraints
- Multiple vehicle support
- Real-time traffic data integration
- Fuel-efficient route calculations

### Intelligent Algorithms
- Machine learning-based prediction models
- Advanced constraint satisfaction routing
- Traffic and fuel consumption optimization
- Dynamic route adjustment

### Driver Management
- Driver portal with route tracking
- Mobile-friendly route navigation
- Proof of delivery capture
- Performance analytics

## 🛠 Technologies Used

### Backend
- Flask
- SQLAlchemy
- Python
- OR-Tools
- Scikit-learn
- Flask-CORS
- Swagger UI
- Gunicorn (recommended for production)

## 🌐 API Services

### Migration API
The Migration API (`migrationApi.py`) provides a comprehensive set of RESTful endpoints for route optimization, geocoding, and data processing. Key features include:

- **Geocoding Services**
  - Convert addresses to geographic coordinates
  - Batch geocoding support
  - Address validation

- **Route Optimization Endpoints**
  - Multiple optimization strategies
  - Traffic-aware routing
  - Fuel-efficient route calculations
  - Multi-vehicle route planning

- **Data Processing**
  - CSV and JSON location data import
  - Location clustering
  - Coordinate processing

- **Predictive Services**
  - Travel time prediction
  - Fuel consumption estimation
  - CO2 emissions calculation

### API Documentation

#### Swagger OpenAPI Specification
The project includes a comprehensive Swagger/OpenAPI specification (`swagger.yaml`) that provides:
- Detailed API endpoint documentation
- Request/response schema definitions
- Interactive API documentation
- Supports Swagger UI for easy exploration

**How to Access Swagger UI**:
- Local development: `/api/docs`
- Describes all available endpoints
- Provides example requests and responses
- Allows direct API testing from the documentation interface

#### Key API Endpoints
- `/api/health`: System health check
- `/api/geocode`: Address to coordinates conversion
- `/api/optimize-route`: AI-powered route optimization
- `/api/predict-travel-time`: Travel time predictions
- `/api/fuel-consumption/predict`: Fuel consumption estimation
- `/api/traffic-data`: Real-time traffic information retrieval

**API Usage Example**:
```python
import requests

# Optimize route
payload = {
    'depot': {'latitude': 40.7128, 'longitude': -74.0060},
    'locations': [
        {'latitude': 40.7282, 'longitude': -73.7949},
        {'latitude': 40.7489, 'longitude': -73.9680}
    ],
    'vehicle_count': 1,
    'use_traffic': True,
    'optimization_objective': 'balanced'
}

response = requests.post('http://your-api-url/api/optimize-route', json=payload)
optimized_routes = response.json()
```

### Machine Learning
- Random Forest Regression
- Gradient Boosting
- Time series prediction
- Fuel consumption modeling

### Frontend
- Bootstrap 5
- Leaflet.js
- Chart.js
- Font Awesome

### Geospatial
- OpenStreetMap
- Nominatim Geocoding
- Traffic Data APIs

## 🔧 Installation

### Prerequisites
- Python 3.8+
- pip
- Virtual environment recommended

### Setup Steps
1. Clone the repository
```bash
git clone https://github.com/yourusername/route-optimization-system.git
cd route-optimization-system
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Initialize database
```bash
flask db upgrade
```

5. Run the application
```bash
flask run
```

## 🌟 Main Components

### Route Optimization
- Calculates most efficient delivery routes
- Considers time windows, vehicle constraints
- Minimizes total distance and fuel consumption

### Fuel Efficiency Modeling
- Predicts fuel consumption
- Tracks actual vs. predicted fuel use
- Generates training data for continuous improvement

### Driver Dashboard
- Real-time route tracking
- Navigation support
- Delivery status updates

### Analytics
- Route performance metrics
- Fuel savings visualization
- Driver efficiency ranking

## 📊 Machine Learning Models

### Fuel Consumption Predictor
- Uses Random Forest Regression
- Considers factors like:
  - Vehicle type
  - Distance
  - Load weight
  - Road conditions
  - Traffic patterns

### Travel Time Predictor
- Estimates route completion times
- Adapts to different road and traffic conditions

## 🔐 Authentication
- JWT-based authentication
- Driver and admin user roles
- Secure route and data access

## 📱 Mobile-Friendly
- Responsive design
- Driver mobile web app
- GPS navigation integration

## 🚢 Deployment
- Supports various deployment options
- Docker containerization ready
- Cloud platform compatible

## 🤝 Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.

## 📧 Contact
Aayush Sharma
---

**Built with ❤️ and AI Technology**