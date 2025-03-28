/**
 * This script creates interactive fuel efficiency visualizations
 * for the route details page.
 */

function initFuelEfficiencyChart(routeData) {
    // Check if we have the required data
    if (!routeData || routeData.length === 0) return;
    
    // Create a container for the chart if it doesn't exist
    let chartContainer = document.getElementById('fuel-efficiency-chart');
    if (!chartContainer) {
        // Find the route summary card
        const routeSummaryCard = document.querySelector('.card-header:contains("Route Summary")').closest('.card');
        if (!routeSummaryCard) return;
        
        // Create and append the chart container
        chartContainer = document.createElement('div');
        chartContainer.id = 'fuel-efficiency-chart';
        chartContainer.className = 'mt-4';
        chartContainer.style.height = '300px';
        
        const chartCard = document.createElement('div');
        chartCard.className = 'card mb-4';
        chartCard.innerHTML = `
            <div class="card-header">
                <h5 class="card-title mb-0">Fuel Efficiency Analysis</h5>
            </div>
            <div class="card-body">
                <div id="fuel-efficiency-chart-container" style="height: 300px;"></div>
            </div>
        `;
        
        // Insert after the route summary card
        routeSummaryCard.after(chartCard);
        chartContainer = document.getElementById('fuel-efficiency-chart-container');
    }
    
    // Prepare data for the chart
    const vehicleLabels = routeData.map((vehicle, index) => `Vehicle ${index + 1}`);
    const distances = routeData.map(vehicle => vehicle.total_distance || 0);
    const fuelConsumption = routeData.map(vehicle => vehicle.total_fuel || 0);
    const fuelSaved = routeData.map(vehicle => vehicle.fuel_saved || 0);
    
    // Calculate fuel efficiency (km/L) for each vehicle
    const fuelEfficiency = distances.map((dist, i) => 
        fuelConsumption[i] > 0 ? dist / fuelConsumption[i] : 0
    );
    
    // Create the chart
    const ctx = document.createElement('canvas');
    chartContainer.appendChild(ctx);
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: vehicleLabels,
            datasets: [
                {
                    label: 'Distance (km)',
                    data: distances,
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Fuel Consumption (L)',
                    data: fuelConsumption,
                    backgroundColor: 'rgba(255, 99, 132, 0.5)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Fuel Saved (L)',
                    data: fuelSaved,
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Efficiency (km/L)',
                    data: fuelEfficiency,
                    type: 'line',
                    backgroundColor: 'rgba(255, 159, 64, 0.5)',
                    borderColor: 'rgba(255, 159, 64, 1)',
                    borderWidth: 2,
                    fill: false,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Distance / Fuel'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Efficiency (km/L)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        footer: function(tooltipItems) {
                            const idx = tooltipItems[0].dataIndex;
                            const vehicle = routeData[idx];
                            
                            if (vehicle && vehicle.total_fuel) {
                                const costSaved = vehicle.cost_saved || (vehicle.fuel_saved * 1.5);
                                const co2Saved = vehicle.fuel_saved * 2.68; // kg CO2 per liter
                                
                                return [
                                    `Cost Saved: $${costSaved.toFixed(2)}`,
                                    `CO₂ Reduced: ${co2Saved.toFixed(2)} kg`
                                ];
                            }
                            return '';
                        }
                    }
                }
            }
        }
    });
    
    // Add a summary section below the chart
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'row text-center mt-3';
    summaryDiv.innerHTML = `
        <div class="col-md-3">
            <h6>Total Distance</h6>
            <p>${distances.reduce((a, b) => a + b, 0).toFixed(2)} km</p>
        </div>
        <div class="col-md-3">
            <h6>Total Fuel</h6>
            <p>${fuelConsumption.reduce((a, b) => a + b, 0).toFixed(2)} L</p>
        </div>
        <div class="col-md-3">
            <h6>Fuel Saved</h6>
            <p class="text-success">${fuelSaved.reduce((a, b) => a + b, 0).toFixed(2)} L</p>
        </div>
        <div class="col-md-3">
            <h6>Avg. Efficiency</h6>
            <p>${(distances.reduce((a, b) => a + b, 0) / fuelConsumption.reduce((a, b) => a + b, 0)).toFixed(2)} km/L</p>
        </div>
    `;
    chartContainer.after(summaryDiv);
}

// Create a fuel consumption breakdown by road type
function createFuelBreakdownChart(routeData) {
    if (!routeData || routeData.length === 0) return;
    
    // Create container
    const container = document.createElement('div');
    container.className = 'card mb-4';
    container.innerHTML = `
        <div class="card-header">
            <h5 class="card-title mb-0">Fuel Consumption Breakdown</h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <canvas id="fuel-by-road-chart" height="250"></canvas>
                </div>
                <div class="col-md-6">
                    <canvas id="fuel-saving-factors-chart" height="250"></canvas>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-12">
                    <h6 class="text-center">Fuel Efficiency Tips</h6>
                    <ul class="list-group">
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            Avoid traffic congestion when possible
                            <span class="badge bg-primary rounded-pill">Up to 30% savings</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            Use highways for long-distance travel
                            <span class="badge bg-primary rounded-pill">Up to 25% savings</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            Optimize stop sequence to minimize distance
                            <span class="badge bg-primary rounded-pill">Up to 20% savings</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            Choose the right vehicle for each route
                            <span class="badge bg-primary rounded-pill">Up to 15% savings</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    `;
    
    // Find the element to insert before
    const targetElement = document.querySelector('#routeAccordion');
    if (targetElement) {
        targetElement.before(container);
    } else {
        // Fallback to appending to a common container
        document.querySelector('.col-md-4').appendChild(container);
    }
    
    // Simulate data for the charts
    const roadTypeData = {
        labels: ['Highway', 'Urban', 'Rural'],
        datasets: [{
            label: 'Fuel Consumption (L)',
            data: [
                routeData.reduce((sum, route) => sum + (route.total_fuel || 0) * 0.5, 0).toFixed(2),  // Highway 50%
                routeData.reduce((sum, route) => sum + (route.total_fuel || 0) * 0.3, 0).toFixed(2),  // Urban 30%
                routeData.reduce((sum, route) => sum + (route.total_fuel || 0) * 0.2, 0).toFixed(2)   // Rural 20%
            ],
            backgroundColor: [
                'rgba(54, 162, 235, 0.5)',
                'rgba(255, 99, 132, 0.5)',
                'rgba(255, 206, 86, 0.5)'
            ],
            borderColor: [
                'rgba(54, 162, 235, 1)',
                'rgba(255, 99, 132, 1)',
                'rgba(255, 206, 86, 1)'
            ],
            borderWidth: 1
        }]
    };
    
    const fuelSavingFactors = {
        labels: ['Route Optimization', 'Traffic Avoidance', 'Vehicle Selection', 'Time Windows'],
        datasets: [{
            label: 'Contribution to Savings (%)',
            data: [40, 30, 20, 10],
            backgroundColor: [
                'rgba(75, 192, 192, 0.5)',
                'rgba(153, 102, 255, 0.5)',
                'rgba(255, 159, 64, 0.5)',
                'rgba(255, 99, 132, 0.5)'
            ],
            borderColor: [
                'rgba(75, 192, 192, 1)',
                'rgba(153, 102, 255, 1)',
                'rgba(255, 159, 64, 1)',
                'rgba(255, 99, 132, 1)'
            ],
            borderWidth: 1
        }]
    };
    
    // Create the charts
    new Chart(document.getElementById('fuel-by-road-chart'), {
        type: 'pie',
        data: roadTypeData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Fuel by Road Type'
                }
            }
        }
    });
    
    new Chart(document.getElementById('fuel-saving-factors-chart'), {
        type: 'doughnut',
        data: fuelSavingFactors,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Fuel Saving Factors'
                }
            }
        }
    });
}

// Initialize after the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Wait for routes data to be available
    if (typeof routeData !== 'undefined') {
        initFuelEfficiencyChart(routeData);
        createFuelBreakdownChart(routeData);
    }
});