# Route Optimizer API - Comprehensive Migration Guide

## Introduction

This comprehensive guide provides detailed information for migrating to and integrating with the Route Optimizer API service. The API is designed to expose sophisticated route optimization algorithms, AI/ML techniques, and logistics functionalities through RESTful endpoints that can be easily consumed by any frontend application, including MERN stacks.

## System Architecture

The Route Optimizer API is built on a Flask backend with the following components:

- **Core API Service**: Handles all HTTP requests and responses
- **ML-based Optimization Modules**: Implements various optimization algorithms
- **Geocoding and Distance Calculation**: Converts addresses to coordinates and calculates distances
- **Traffic Data Integration**: Incorporates real-time traffic information
- **Fuel Efficiency Estimation**: Uses AI to predict and optimize fuel consumption

The service follows a RESTful architecture with JSON as the primary data exchange format. For file uploads, the API supports multipart/form-data content type.

## API Endpoints - Detailed Reference

### System Operations

#### Health Check
- **Endpoint**: `GET /api/health`
- **Description**: Simple health check to ensure the API is running
- **Response**: Status information and API version
- **Use Case**: Monitoring and availability checks
- **Example Response**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2025-03-28T12:34:56Z",
    "version": "1.0.0"
  }
  ```

### Geocoding and Location Services

#### Geocode Addresses
- **Endpoint**: `POST /api/geocode`
- **Description**: Converts textual addresses into geographic coordinates (latitude/longitude)
- **Request Body**: 
  ```json
  {
    "addresses": ["123 Main St, New York, NY", "456 Park Ave, Miami, FL"]
  }
  ```
- **Response**: Mapping of addresses to coordinates
- **Key Parameters**: 
  - `addresses`: Array of address strings
- **Use Case**: Converting user-entered addresses to mappable coordinates
- **Example Response**:
  ```json
  {
    "results": {
      "123 Main St, New York, NY": {
        "latitude": 40.7128,
        "longitude": -74.0060
      },
      "456 Park Ave, Miami, FL": {
        "latitude": 25.7617,
        "longitude": -80.1918
      }
    },
    "count": {
      "total": 2,
      "successful": 2
    }
  }
  ```

#### Calculate Distance Matrix
- **Endpoint**: `POST /api/distance-matrix`
- **Description**: Calculates distances between multiple coordinates
- **Request Body**:
  ```json
  {
    "coordinates": [
      {"lat": 40.7128, "lng": -74.0060},
      {"lat": 40.7300, "lng": -73.9950},
      {"lat": 40.7400, "lng": -74.0100}
    ]
  }
  ```
- **Response**: 2D matrix of distances between all points
- **Key Parameters**:
  - `coordinates`: Array of objects with lat/lng properties
- **Use Case**: Pre-calculation step for route optimization
- **Example Response**:
  ```json
  {
    "matrix": [
      [0, 2.5, 3.2],
      [2.5, 0, 1.8],
      [3.2, 1.8, 0]
    ],
    "size": 3,
    "unit": "kilometers"
  }
  ```

#### Process Location Data
- **Endpoint**: `POST /api/process-locations`
- **Description**: Process location data from JSON objects or CSV files
- **Content Types**:
  - `application/json`: For JSON data
  - `multipart/form-data`: For file uploads
- **JSON Request Example**:
  ```json
  {
    "locations": [
      {
        "name": "Customer A",
        "address": "123 Main St, New York, NY"
      },
      {
        "name": "Customer B",
        "address": "456 Park Ave, Miami, FL",
        "latitude": 25.7617,
        "longitude": -80.1918
      }
    ]
  }
  ```
- **Response**: Processed locations with geocoded coordinates when possible
- **Use Case**: Batch processing of location data
- **Notes**: Will attempt to geocode addresses without coordinates

#### Upload CSV File
- **Endpoint**: `POST /api/upload-csv`
- **Description**: Dedicated endpoint for uploading CSV files with location data
- **Content Type**: `multipart/form-data`
- **Form Parameters**:
  - `file`: CSV file with location data
- **Expected CSV Format**:
  ```
  name,address,latitude,longitude,time_window_start,time_window_end
  Warehouse,123 Main St,40.7128,-74.0060,08:00,18:00
  Customer A,456 Park Ave,,,09:00,12:00
  ```
- **Response**: Processed locations with geocoded coordinates
- **Use Case**: Bulk import of locations from spreadsheets or exports from other systems
- **Example Response**:
  ```json
  {
    "locations": [
      {
        "name": "Warehouse",
        "address": "123 Main St",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "time_window_start": "08:00",
        "time_window_end": "18:00"
      },
      {
        "name": "Customer A",
        "address": "456 Park Ave",
        "latitude": 40.7300,
        "longitude": -73.9950,
        "time_window_start": "09:00",
        "time_window_end": "12:00"
      }
    ],
    "count": 2,
    "geocoded": 1,
    "message": "CSV imported successfully"
  }
  ```

### Route Optimization

#### Optimize Route
- **Endpoint**: `POST /api/optimize-route`
- **Description**: Core endpoint for generating optimized delivery routes
- **Request Body**:
  ```json
  {
    "depot": {
      "id": 1,
      "name": "Warehouse",
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "locations": [
      {
        "id": 2,
        "name": "Customer A",
        "latitude": 40.7300,
        "longitude": -73.9950,
        "time_window_start": "09:00",
        "time_window_end": "12:00"
      },
      {
        "id": 3,
        "name": "Customer B",
        "latitude": 40.7400,
        "longitude": -74.0100,
        "time_window_start": "13:00",
        "time_window_end": "16:00"
      }
    ],
    "vehicle_count": 1,
    "use_traffic": true,
    "use_fuel_efficient": false,
    "optimization_objective": "balanced"
  }
  ```
- **Key Parameters**:
  - `depot`: Starting and ending location
  - `locations`: Array of delivery locations
  - `vehicle_count`: Number of vehicles to use
  - `use_traffic`: Whether to consider real-time traffic
  - `use_fuel_efficient`: Whether to optimize for fuel efficiency
  - `optimization_objective`: What to optimize for (distance, time, fuel, balanced)
- **Response**: Optimized routes with detailed stop information
- **Advanced Features**:
  - Time window constraints for deliveries
  - Multi-vehicle routing
  - Traffic-aware optimization
  - Fuel-efficient routing
- **Example Response**:
  ```json
  {
    "routes": [
      {
        "vehicle_id": 0,
        "vehicle_type": "van",
        "stops": [
          {
            "id": 1,
            "name": "Warehouse",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "is_depot": true
          },
          {
            "id": 2,
            "name": "Customer A",
            "latitude": 40.7300,
            "longitude": -73.9950,
            "is_depot": false,
            "time_window_start": "09:00",
            "time_window_end": "12:00",
            "traffic_factor": 1.2,
            "leg_distance": 2.5,
            "leg_time": 0.15,
            "leg_fuel": 0.3
          },
          {
            "id": 3,
            "name": "Customer B",
            "latitude": 40.7400,
            "longitude": -74.0100,
            "is_depot": false,
            "time_window_start": "13:00",
            "time_window_end": "16:00",
            "traffic_factor": 1.1,
            "leg_distance": 1.8,
            "leg_time": 0.10,
            "leg_fuel": 0.2
          },
          {
            "id": 1,
            "name": "Warehouse",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "is_depot": true
          }
        ],
        "total_distance": 7.5,
        "total_time": 0.35,
        "total_fuel": 0.8,
        "fuel_saved": 0.1,
        "traffic_impact": 5.2
      }
    ],
    "optimization_type": "traffic_aware",
    "vehicle_count": 1,
    "total_locations": 2,
    "timestamp": "2025-03-28T12:34:56Z",
    "traffic_info": {
      "congestion_areas": 5,
      "traffic_signals": 12,
      "is_simulated": false,
      "timestamp": "2025-03-28T12:34:56Z"
    }
  }
  ```

#### Predict Travel Time
- **Endpoint**: `POST /api/predict-travel-time`
- **Description**: Uses ML techniques to predict travel times based on distances
- **Request Body**:
  ```json
  {
    "distances": [10.5, 15.2, 8.7],
    "time_of_day": "08:30",
    "day_of_week": "monday"
  }
  ```
- **Response**: Predicted travel times in hours
- **Key Parameters**:
  - `distances`: Array of distances in kilometers
  - `time_of_day`: Time of day (affects traffic patterns)
  - `day_of_week`: Day of week (affects traffic patterns)
- **Use Case**: Time-sensitive delivery planning

### Traffic Data

#### Get Traffic Data
- **Endpoint**: `GET /api/traffic-data`
- **Description**: Retrieves real-time or simulated traffic information for an area
- **Query Parameters**:
  - `min_lat`: Minimum latitude of bounding box
  - `min_lon`: Minimum longitude of bounding box
  - `max_lat`: Maximum latitude of bounding box
  - `max_lon`: Maximum longitude of bounding box
- **Example**: `/api/traffic-data?min_lat=40.70&min_lon=-74.10&max_lat=40.80&max_lon=-73.90`
- **Response**: Traffic signals, congestion areas, and road speeds
- **Use Case**: Traffic visualization, route planning with traffic considerations

### Fuel Consumption

#### Predict Fuel Consumption
- **Endpoint**: `POST /api/fuel-consumption/predict`
- **Description**: Uses ML model to predict fuel consumption based on various factors
- **Request Body**:
  ```json
  {
    "distance": 50.5,
    "vehicle_type": "van",
    "vehicle_weight": 2500,
    "load_weight": 800,
    "avg_speed": 60,
    "traffic_factor": 1.2,
    "stop_frequency": 0.2,
    "road_type": "mixed",
    "gradient": 0,
    "temperature": 20,
    "fuel_type": "diesel"
  }
  ```
- **Response**: Predicted fuel consumption and CO2 emissions
- **Key Parameters**: Various vehicle and route characteristics
- **Use Case**: Eco-friendly route planning, fuel cost estimation
- **Example Response**:
  ```json
  {
    "fuel_consumption": 5.2,
    "unit": "liters",
    "co2_emissions": 13.9,
    "co2_unit": "kg"
  }
  ```

#### Record Actual Fuel Consumption
- **Endpoint**: `POST /api/fuel-consumption/record`
- **Description**: Records actual fuel consumption for model improvement
- **Request Body**:
  ```json
  {
    "route_id": 123,
    "vehicle_id": 456,
    "actual_fuel": 12.5,
    "driver_id": 789,
    "metadata": {
      "load_weight": 800,
      "avg_speed": 55,
      "traffic_factor": 1.3,
      "road_type": "mixed",
      "temperature": 22,
      "weather": "clear",
      "driver_efficiency": 0.95
    }
  }
  ```
- **Response**: Confirmation of recorded data
- **Use Case**: Model training, driver efficiency analysis
- **Note**: Improves prediction accuracy over time

### Clustering

#### Cluster Locations
- **Endpoint**: `POST /api/clusters`
- **Description**: Groups locations into clusters for multi-vehicle routing
- **Request Body**:
  ```json
  {
    "locations": [
      {"id": 1, "latitude": 40.7128, "longitude": -74.0060},
      {"id": 2, "latitude": 40.7300, "longitude": -73.9950},
      {"id": 3, "latitude": 40.7400, "longitude": -74.0100},
      {"id": 4, "latitude": 25.7617, "longitude": -80.1918},
      {"id": 5, "latitude": 25.7500, "longitude": -80.2000}
    ],
    "num_clusters": 2
  }
  ```
- **Response**: Groups of location indices by cluster
- **Key Parameters**:
  - `locations`: Array of location objects
  - `num_clusters`: Number of clusters to create
- **Use Case**: Assigning locations to multiple vehicles
- **Example Response**:
  ```json
  {
    "clusters": [
      {
        "cluster_id": 0,
        "location_indices": [0, 1, 2],
        "size": 3
      },
      {
        "cluster_id": 1,
        "location_indices": [3, 4],
        "size": 2
      }
    ],
    "num_clusters": 2,
    "total_locations": 5
  }
  ```

## Integration Patterns

### Basic Integration Flow

1. **Collect Delivery Locations**
   - Use the `/api/geocode` endpoint to convert addresses to coordinates
   - Alternatively, upload a CSV file via `/api/upload-csv`

2. **Optimize Routes**
   - Call `/api/optimize-route` with the depot and delivery locations
   - Specify optimization preferences (traffic awareness, fuel efficiency)

3. **Display and Use Results**
   - Render routes on a map
   - Display turn-by-turn directions
   - Calculate estimated arrival times and fuel usage

### Advanced Optimization Techniques

#### Using Time Windows

Time windows allow you to specify when deliveries must occur:

```json
{
  "depot": {...},
  "locations": [
    {
      "id": 2,
      "name": "Customer A",
      "latitude": 40.7300,
      "longitude": -73.9950,
      "time_window_start": "09:00",
      "time_window_end": "12:00"
    },
    ...
  ]
}
```

The optimizer will sequence stops to satisfy these constraints while minimizing overall distance/time.

#### Multi-Vehicle Routing

To use multiple vehicles:

```json
{
  "depot": {...},
  "locations": [...],
  "vehicle_count": 3
}
```

You can also pre-cluster locations by using the `/api/clusters` endpoint first.

#### Fuel-Efficient Routing

Enable fuel-efficient routing by setting:

```json
{
  "use_fuel_efficient": true,
  "optimization_objective": "fuel"
}
```

For even more control, specify vehicle types:

```json
{
  "vehicle_count": 2,
  "vehicle_type_0": "truck",
  "vehicle_type_1": "van"
}
```

#### Traffic-Aware Routing

Enable traffic consideration:

```json
{
  "use_traffic": true
}
```

This incorporates real-time or predicted traffic conditions into the optimization.

## MERN Stack Integration Examples

### React Frontend Example

```jsx
import React, { useState } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';

const RouteOptimizer = () => {
  const [depot, setDepot] = useState({ id: 1, name: 'Warehouse', latitude: 40.7128, longitude: -74.0060 });
  const [locations, setLocations] = useState([]);
  const [optimizedRoutes, setOptimizedRoutes] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/api/upload-csv', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      setLocations(response.data.locations);
    } catch (error) {
      console.error('Error uploading CSV:', error);
      alert('Failed to upload file');
    } finally {
      setLoading(false);
    }
  };

  const optimizeRoute = async () => {
    if (locations.length === 0) {
      alert('Please add delivery locations first');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/api/optimize-route', {
        depot,
        locations,
        vehicle_count: 1,
        use_traffic: true,
        use_fuel_efficient: true,
        optimization_objective: 'balanced'
      });
      setOptimizedRoutes(response.data.routes);
    } catch (error) {
      console.error('Error optimizing route:', error);
      alert('Failed to optimize route');
    } finally {
      setLoading(false);
    }
  };

  // Generate a color for each route
  const getRouteColor = (index) => {
    const colors = ['blue', 'red', 'green', 'purple', 'orange'];
    return colors[index % colors.length];
  };

  return (
    <div className="container mt-4">
      <h1>Route Optimizer</h1>
      
      <div className="mb-3">
        <label htmlFor="csv-upload" className="form-label">Upload Locations (CSV)</label>
        <input 
          className="form-control" 
          type="file" 
          id="csv-upload" 
          accept=".csv"
          onChange={handleFileUpload} 
        />
      </div>
      
      <button 
        className="btn btn-primary mb-4" 
        onClick={optimizeRoute}
        disabled={loading || locations.length === 0}
      >
        {loading ? 'Processing...' : 'Optimize Route'}
      </button>
      
      {locations.length > 0 && (
        <div className="mb-3">
          <h3>Delivery Locations ({locations.length})</h3>
          <ul className="list-group">
            {locations.slice(0, 5).map((loc) => (
              <li key={loc.id} className="list-group-item">
                {loc.name}: {loc.address}
              </li>
            ))}
            {locations.length > 5 && <li className="list-group-item text-muted">...and {locations.length - 5} more</li>}
          </ul>
        </div>
      )}
      
      {optimizedRoutes && (
        <div>
          <h3>Optimized Routes</h3>
          
          <div className="row">
            <div className="col-md-4">
              {optimizedRoutes.map((route, i) => (
                <div key={i} className="card mb-3">
                  <div className="card-header">
                    Vehicle {route.vehicle_id} ({route.vehicle_type})
                  </div>
                  <div className="card-body">
                    <p>Total Distance: {route.total_distance.toFixed(2)} km</p>
                    <p>Total Time: {(route.total_time * 60).toFixed(0)} minutes</p>
                    <p>Total Fuel: {route.total_fuel?.toFixed(2)} liters</p>
                    {route.fuel_saved && <p>Fuel Saved: {route.fuel_saved.toFixed(2)} liters</p>}
                    <h6>Stops ({route.stops.length})</h6>
                    <ol className="small">
                      {route.stops.map((stop, j) => (
                        <li key={j} className={stop.is_depot ? 'text-primary' : ''}>
                          {stop.name} {stop.time_window_start ? `(${stop.time_window_start}-${stop.time_window_end})` : ''}
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="col-md-8">
              <div style={{ height: '500px' }}>
                <MapContainer center={[depot.latitude, depot.longitude]} zoom={12} style={{ height: '100%' }}>
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  
                  {/* Depot Marker */}
                  <Marker position={[depot.latitude, depot.longitude]}>
                    <Popup>Depot: {depot.name}</Popup>
                  </Marker>
                  
                  {/* Routes */}
                  {optimizedRoutes.map((route, i) => {
                    const positions = route.stops.map(stop => [stop.latitude, stop.longitude]);
                    return (
                      <Polyline 
                        key={i}
                        positions={positions}
                        color={getRouteColor(i)}
                        weight={4}
                      />
                    );
                  })}
                  
                  {/* Stop Markers */}
                  {optimizedRoutes.flatMap(route => 
                    route.stops.filter(stop => !stop.is_depot).map((stop, j) => (
                      <Marker key={`${stop.id}-${j}`} position={[stop.latitude, stop.longitude]}>
                        <Popup>
                          {stop.name}<br/>
                          {stop.time_window_start && `Time: ${stop.time_window_start}-${stop.time_window_end}`}
                        </Popup>
                      </Marker>
                    ))
                  )}
                </MapContainer>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RouteOptimizer;
```

### Node.js Backend Integration Example

```javascript
const express = require('express');
const axios = require('axios');
const multer = require('multer');
const fs = require('fs');
const path = require('path');

const app = express();
const upload = multer({ dest: 'uploads/' });

// Parse JSON bodies
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API base URL
const API_BASE_URL = 'http://localhost:5000/api';

// Proxy endpoint for route optimization
app.post('/optimize', async (req, res) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/optimize-route`, req.body);
    res.json(response.data);
  } catch (error) {
    console.error('Error optimizing route:', error.response?.data || error.message);
    res.status(error.response?.status || 500).json({
      error: error.response?.data?.error || 'Failed to optimize route'
    });
  }
});

// Handle CSV uploads
app.post('/upload-locations', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    
    // Create form data
    const formData = new FormData();
    formData.append('file', fs.createReadStream(req.file.path), {
      filename: req.file.originalname,
      contentType: 'text/csv'
    });
    
    // Send to Route Optimizer API
    const response = await axios.post(`${API_BASE_URL}/upload-csv`, formData, {
      headers: {
        ...formData.getHeaders()
      }
    });
    
    // Delete temporary file
    fs.unlinkSync(req.file.path);
    
    res.json(response.data);
  } catch (error) {
    console.error('Error processing CSV:', error.response?.data || error.message);
    
    // Clean up temp file if it exists
    if (req.file && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }
    
    res.status(error.response?.status || 500).json({
      error: error.response?.data?.error || 'Failed to process CSV file'
    });
  }
});

// Get traffic data
app.get('/traffic', async (req, res) => {
  try {
    // Forward query parameters
    const response = await axios.get(`${API_BASE_URL}/traffic-data`, {
      params: req.query
    });
    res.json(response.data);
  } catch (error) {
    console.error('Error fetching traffic data:', error.response?.data || error.message);
    res.status(error.response?.status || 500).json({
      error: error.response?.data?.error || 'Failed to fetch traffic data'
    });
  }
});

// Geocode addresses
app.post('/geocode', async (req, res) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/geocode`, req.body);
    res.json(response.data);
  } catch (error) {
    console.error('Error geocoding addresses:', error.response?.data || error.message);
    res.status(error.response?.status || 500).json({
      error: error.response?.data?.error || 'Failed to geocode addresses'
    });
  }
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
```

## Performance Considerations

### Optimization for Large Datasets

When dealing with large numbers of locations (>50):

1. **Pre-Clustering**: Use the `/api/clusters` endpoint to group locations before optimization
2. **Multiple Vehicles**: Set `vehicle_count` to spread the workload
3. **Staggered Requests**: For very large datasets, split into multiple optimization requests

### Reducing API Calls

1. **Cache Geocoding Results**: Store the results of geocoding operations to avoid redundant API calls
2. **Batch Processing**: Use the batch endpoints when possible (e.g., geocoding multiple addresses at once)
3. **Retain Distance Matrices**: Store and reuse distance matrices for commonly used location sets

### Network and Timeout Considerations

1. **Implement Retries**: Some optimization operations can take time; implement retry logic for network issues
2. **Increase Timeouts**: Set longer timeouts for route optimization requests
3. **Progress Indicators**: Use loading indicators for operations that may take several seconds

## Error Handling

All API endpoints return standardized error responses with HTTP status codes:

- **400 Bad Request**: Missing or invalid parameters
- **500 Internal Server Error**: Server-side errors

Error responses follow this format:
```json
{
  "error": "Detailed error message"
}
```

Implement proper error handling in your client applications to gracefully handle these cases.

## Security Considerations

While the current implementation does not include authentication, for production deployments consider:

1. **API Key Authentication**: Add API key validation for all requests
2. **Rate Limiting**: Implement request throttling to prevent abuse
3. **HTTPS**: Always use HTTPS in production environments
4. **Input Validation**: Validate all inputs on both client and server sides
5. **CORS Restrictions**: Limit CORS to specific origins in production

## Testing the API

The API includes Swagger documentation available at `/api/docs` which provides an interactive interface for testing all endpoints. Use this to explore the API capabilities and understand the request/response formats.

## CSV File Format

For the `/api/upload-csv` endpoint, the expected CSV format is:

```
name,address,latitude,longitude,time_window_start,time_window_end
Warehouse,123 Main St New York,40.7128,-74.0060,08:00,18:00
Customer A,456 Park Ave,,,09:00,12:00
Customer B,789 Broadway,,,13:00,16:00
```

Notes:
- The header row is required
- Latitude and longitude are optional; the API will geocode addresses if coordinates are missing
- Time windows are optional
- Time format should be HH:MM in 24-hour format

## Conclusion

The Route Optimizer API provides a comprehensive set of tools for logistics optimization. By following this guide, you should be able to successfully integrate these capabilities into your applications, leveraging advanced AI/ML techniques for route planning, fuel efficiency, and more.

For any additional questions or support, please contact the API development team.