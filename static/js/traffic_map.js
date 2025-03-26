// Traffic Map Visualization
const TrafficMap = {
    // Traffic layer
    trafficLayer: null,
    
    // Map instance
    map: null,
    
    // Traffic data
    trafficData: null,
    
    // Initialize the traffic layer on a map
    init: function(map) {
        this.map = map;
        this.trafficLayer = L.layerGroup().addTo(map);
        
        // Add traffic toggle control
        this.addTrafficControl();
        
        return this;
    },
    
    // Add traffic toggle button to map
    addTrafficControl: function() {
        const trafficControl = L.control({position: 'topright'});
        
        trafficControl.onAdd = (map) => {
            const div = L.DomUtil.create('div', 'traffic-control');
            div.innerHTML = `
                <button class="btn btn-sm btn-primary" id="toggle-traffic" title="Toggle Traffic Layer">
                    <i class="fas fa-traffic-light"></i>
                </button>
            `;
            
            // Prevent map click events when clicking the control
            L.DomEvent.disableClickPropagation(div);
            
            // Add event listener after DOM element is added to the map
            setTimeout(() => {
                document.getElementById('toggle-traffic').addEventListener('click', () => {
                    this.toggleTrafficLayer();
                });
            }, 100);
            
            return div;
        };
        
        trafficControl.addTo(this.map);
    },
    
    // Toggle traffic layer visibility
    toggleTrafficLayer: function() {
        if (!this.trafficData) {
            this.fetchTrafficData();
            return;
        }
        
        if (this.map.hasLayer(this.trafficLayer)) {
            this.map.removeLayer(this.trafficLayer);
            document.getElementById('toggle-traffic').classList.replace('btn-danger', 'btn-primary');
        } else {
            this.trafficLayer.addTo(this.map);
            document.getElementById('toggle-traffic').classList.replace('btn-primary', 'btn-danger');
        }
    },
    
    // Fetch traffic data from the API
    fetchTrafficData: function() {
        // Show loading indicator
        document.getElementById('toggle-traffic').innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
        
        // Get map bounds
        const bounds = this.map.getBounds();
        const minLat = bounds.getSouth();
        const minLon = bounds.getWest();
        const maxLat = bounds.getNorth();
        const maxLon = bounds.getEast();
        
        // Fetch traffic data from API
        fetch(`/api/traffic?min_lat=${minLat}&min_lon=${minLon}&max_lat=${maxLat}&max_lon=${maxLon}`)
            .then(response => response.json())
            .then(data => {
                this.trafficData = data;
                this.visualizeTrafficData();
                document.getElementById('toggle-traffic').innerHTML = '<i class="fas fa-traffic-light"></i>';
                document.getElementById('toggle-traffic').classList.replace('btn-primary', 'btn-danger');
            })
            .catch(error => {
                console.error('Error fetching traffic data:', error);
                document.getElementById('toggle-traffic').innerHTML = '<i class="fas fa-exclamation-triangle"></i>';
                
                // Show error toast
                showToast('Failed to load traffic data. Using simulated data instead.', 'warning');
                
                // Simulate traffic data
                this.simulateTrafficData();
            });
    },
    
    // Simulate traffic data when API fails
    simulateTrafficData: function() {
        const bounds = this.map.getBounds();
        const center = bounds.getCenter();
        
        // Create simulated traffic data
        this.trafficData = {
            is_simulated: true,
            traffic_signals: [],
            congestion_areas: []
        };
        
        // Add simulated traffic signals
        for (let i = 0; i < 10; i++) {
            const lat = center.lat + (Math.random() * 0.05 - 0.025);
            const lon = center.lng + (Math.random() * 0.05 - 0.025);
            
            this.trafficData.traffic_signals.push({
                lat: lat,
                lon: lon
            });
        }
        
        // Add simulated congestion areas
        for (let i = 0; i < 5; i++) {
            const centerLat = center.lat + (Math.random() * 0.05 - 0.025);
            const centerLon = center.lng + (Math.random() * 0.05 - 0.025);
            
            const coords = [];
            const points = Math.floor(Math.random() * 4) + 3; // 3-6 points
            
            for (let j = 0; j < points; j++) {
                const lat = centerLat + (Math.random() * 0.01 - 0.005);
                const lon = centerLon + (Math.random() * 0.01 - 0.005);
                coords.push({ lat, lon });
            }
            
            this.trafficData.congestion_areas.push({
                way_id: `sim_${i}`,
                coords: coords,
                congestion_level: Math.random() * 0.6 + 0.2 // 0.2 to 0.8
            });
        }
        
        this.visualizeTrafficData();
        document.getElementById('toggle-traffic').innerHTML = '<i class="fas fa-traffic-light"></i>';
        document.getElementById('toggle-traffic').classList.replace('btn-primary', 'btn-danger');
    },
    
    // Visualize traffic data on the map
    visualizeTrafficData: function() {
        // Clear previous traffic layer
        this.trafficLayer.clearLayers();
        
        // Add traffic signals to the map
        if (this.trafficData.traffic_signals) {
            this.trafficData.traffic_signals.forEach(signal => {
                const marker = L.circleMarker([signal.lat, signal.lon], {
                    radius: 5,
                    fillColor: '#ff0000',
                    color: '#000',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }).bindPopup('Traffic Signal');
                
                this.trafficLayer.addLayer(marker);
            });
        }
        
        // Add congestion areas to the map
        if (this.trafficData.congestion_areas) {
            this.trafficData.congestion_areas.forEach(area => {
                if (!area.coords || area.coords.length < 3) return;
                
                // Convert coordinates to Leaflet format
                const points = area.coords.map(coord => [coord.lat, coord.lon]);
                
                // Get color based on congestion level (red for high, yellow for medium, orange for low)
                let color = '#ff0000'; // Default red
                if (area.congestion_level < 0.4) {
                    color = '#ffa500'; // Orange for low congestion
                } else if (area.congestion_level < 0.7) {
                    color = '#ffff00'; // Yellow for medium congestion
                }
                
                // Create polygon for congestion area
                const polygon = L.polygon(points, {
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.3,
                    weight: 2
                }).bindPopup(`Congestion Level: ${Math.round(area.congestion_level * 100)}%`);
                
                this.trafficLayer.addLayer(polygon);
            });
        }
        
        // Add layer to map if not already added
        if (!this.map.hasLayer(this.trafficLayer)) {
            this.trafficLayer.addTo(this.map);
        }
    },
    
    // Update traffic data for a specific route
    updateRouteTraffic: function(routeLines) {
        if (!this.trafficData) return;
        
        // Loop through each route line
        routeLines.forEach(routeLine => {
            const latLngs = routeLine.getLatLngs();
            let hasTraffic = false;
            
            // Check if route passes through congestion areas
            if (this.trafficData.congestion_areas) {
                for (const area of this.trafficData.congestion_areas) {
                    if (!area.coords || area.coords.length < 3) continue;
                    
                    const polygonPoints = area.coords.map(coord => [coord.lat, coord.lon]);
                    const polygon = L.polygon(polygonPoints);
                    
                    // Check if any point of the route is inside the congestion area
                    for (const latLng of latLngs) {
                        if (this.isPointInPolygon(latLng, polygonPoints)) {
                            hasTraffic = true;
                            
                            // Update route style based on congestion level
                            const dashArray = `${5 + Math.round(area.congestion_level * 10)}, ${5 + Math.round(area.congestion_level * 5)}`;
                            routeLine.setStyle({
                                dashArray: dashArray,
                                color: area.congestion_level > 0.6 ? '#ff0000' : '#ffa500'
                            });
                            
                            break;
                        }
                    }
                    
                    if (hasTraffic) break;
                }
            }
        });
    },
    
    // Helper function to check if a point is inside a polygon
    isPointInPolygon: function(point, polygon) {
        const x = point.lat;
        const y = point.lng;
        
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i][0];
            const yi = polygon[i][1];
            const xj = polygon[j][0];
            const yj = polygon[j][1];
            
            const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        
        return inside;
    }
};

// Function to add traffic information to route map
function addTrafficToRouteMap(map, routeData) {
    // Initialize traffic map
    const trafficMap = TrafficMap.init(map);
    
    // Store route lines for later traffic updates
    const routeLines = [];
    
    // Find all polylines that were added to the map (route lines)
    map.eachLayer(layer => {
        if (layer instanceof L.Polyline && !(layer instanceof L.Polygon)) {
            routeLines.push(layer);
        }
    });
    
    // Fetch traffic data after a short delay (to ensure map is fully loaded)
    setTimeout(() => {
        trafficMap.fetchTrafficData();
        
        // Add event listener to update traffic when map is moved
        map.on('moveend', () => {
            if (trafficMap.trafficData && map.hasLayer(trafficMap.trafficLayer)) {
                trafficMap.fetchTrafficData();
            }
        });
        
        // Update route lines with traffic information once data is loaded
        const checkTrafficData = setInterval(() => {
            if (trafficMap.trafficData) {
                trafficMap.updateRouteTraffic(routeLines);
                clearInterval(checkTrafficData);
            }
        }, 500);
    }, 1000);
}