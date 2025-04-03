// Driver Route JavaScript
document.addEventListener("DOMContentLoaded", function () {
  // Global variables
  let map;
  let routeData;
  let deliveryStops = [];
  let currentLocation;
  let routingControl;
  let activeStopId = null;
  let markers = [];
  let watchId = null;
  let signaturePad;
  let routeId;
  let pendingStops = [];
  let activeIncident = null;
  let incidentCheckInterval = null;

  // Extract route ID from URL
  const pathSegments = window.location.pathname.split("/");
  routeId = pathSegments[pathSegments.length - 1];

  // Initialize the map
  function initMap() {
    // Create map
    map = L.map("map").setView([40.7128, -74.006], 13);

    // Add tile layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    // Add location buttons
    addMapControls();

    // Load route data
    loadRouteData();
  }

  // Add map control buttons
  function addMapControls() {
    // Add locate button
    const locateBtn = L.DomUtil.create("div", "btn-floating btn-locate");
    locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i>';
    locateBtn.onclick = centerOnCurrentLocation;
    map.getContainer().appendChild(locateBtn);
  }

  // Function to load route data
  function loadRouteData() {
    fetch(`/driver/routes/${routeId}`, {
      headers: {
        Authorization: "Bearer " + getToken(),
      },
    })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 401) {
            // Redirect to login if unauthorized
            window.location.href = "/driver/login";
            return;
          }
          throw new Error("Failed to load route");
        }
        return response.json();
      })
      .then((data) => {
        routeData = data;
        deliveryStops = data.delivery_stops;

        // Update UI
        updateRouteInfo();

        // Render stops
        renderStops();

        // Add markers to map
        addRouteMarkers();

        // Request location permission
        requestLocationPermission();
      })
      .catch((error) => {
        console.error("Error loading route data:", error);
        showToast("Failed to load route data", "danger");
      });
  }

  // Function to update route information in header
  function updateRouteInfo() {
    document.getElementById("route-name").textContent =
      routeData.route_details.name || "Route " + routeId;

    // Calculate completed stops
    const completedStops = deliveryStops.filter(
      (stop) => stop.status === "completed" || stop.status === "failed"
    ).length;
    const totalStops = deliveryStops.length;

    document.getElementById(
      "route-stops-info"
    ).textContent = `${completedStops}/${totalStops} stops completed`;
    document.getElementById(
      "route-distance-info"
    ).textContent = `${routeData.route_details.total_distance.toFixed(1)} km`;

    // Enable/disable complete route button based on status
    const completeRouteBtn = document.getElementById("complete-route-btn");
    if (routeData.driver_route.status === "completed") {
      completeRouteBtn.classList.add("disabled");
      completeRouteBtn.innerHTML =
        '<i class="fas fa-check-circle me-2"></i>Completed';
    }
  }

  // Function to render stops in the bottom panel
  function renderStops() {
    const stopsList = document.getElementById("stops-list");
    stopsList.innerHTML = "";

    if (deliveryStops.length === 0) {
      stopsList.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-map-marker-alt fa-3x text-muted mb-3"></i>
                    <p>No stops on this route.</p>
                </div>
            `;
      return;
    }

    // Sort stops by stop number
    deliveryStops.sort((a, b) => a.stop_number - b.stop_number);

    // Find first non-completed stop to mark as active
    if (!activeStopId) {
      const nextStop = deliveryStops.find(
        (stop) => stop.status === "pending" || stop.status === "arrived"
      );
      if (nextStop) {
        activeStopId = nextStop.id;
      }
    }

    // Create stop cards
    deliveryStops.forEach((stop) => {
      const template = document.getElementById("stop-card-template");
      const card = document
        .importNode(template.content, true)
        .querySelector(".card");

      // Set data attributes
      card.dataset.stopId = stop.id;

      // Add appropriate class based on status
      if (stop.status === "completed") {
        card.classList.add("completed");
      } else if (stop.status === "failed") {
        card.classList.add("failed");
      } else if (stop.id == activeStopId) {
        card.classList.add("active");
      }

      // Set card content
      card.querySelector(".stop-name").textContent = stop.location_name;
      card.querySelector(".stop-address").textContent = stop.location_address;
      card.querySelector(".stop-number").textContent = stop.stop_number;

      // Set time window if available
      const timeWindowElement = card.querySelector(".time-window");
      if (stop.time_window_start && stop.time_window_end) {
        timeWindowElement.innerHTML = `<i class="fas fa-clock"></i> ${formatTimeWindow(
          stop.time_window_start,
          stop.time_window_end
        )}`;

        // Check if we're outside the time window
        const now = new Date();
        const startTime = parseTimeString(stop.time_window_start);
        const endTime = parseTimeString(stop.time_window_end);

        if (now < startTime) {
          timeWindowElement.classList.add("warning");
        } else if (now > endTime) {
          timeWindowElement.classList.add("danger");
        }
      } else {
        timeWindowElement.parentNode.removeChild(timeWindowElement);
      }

      // Set status indicator
      const statusElement = card.querySelector(".stop-status");
      statusElement.classList.add(`status-${stop.status}`);
      statusElement.title = capitalizeFirstLetter(stop.status);

      // Set up button event listeners
      const navigateBtn = card.querySelector(".navigate-btn");
      const arrivedBtn = card.querySelector(".arrived-btn");
      const completeBtn = card.querySelector(".complete-btn");

      navigateBtn.addEventListener("click", () => {
        navigateToStop(stop);
      });

      arrivedBtn.addEventListener("click", () => {
        markStopAsArrived(stop.id);
      });

      completeBtn.addEventListener("click", () => {
        openDeliveryActionModal(stop.id);
      });

      // Disable buttons based on status
      if (stop.status === "arrived") {
        arrivedBtn.disabled = true;
        arrivedBtn.classList.add("disabled");
      } else if (stop.status === "completed" || stop.status === "failed") {
        navigateBtn.disabled = true;
        arrivedBtn.disabled = true;
        completeBtn.disabled = true;
        navigateBtn.classList.add("disabled");
        arrivedBtn.classList.add("disabled");
        completeBtn.classList.add("disabled");
      }

      // Add click event to the card
      card.addEventListener("click", (e) => {
        // Don't trigger if clicked on a button
        if (e.target.tagName === "BUTTON" || e.target.closest("button")) {
          return;
        }

        setActiveStop(stop.id);
      });

      stopsList.appendChild(card);
    });
  }

  // Function to add markers to the map
  function addRouteMarkers() {
    // Clear existing markers
    markers.forEach((marker) => map.removeLayer(marker));
    markers = [];

    // Add depot marker (first and last stops from route details)
    const routeStops = routeData.route_details.stops;
    if (routeStops && routeStops.length > 0) {
      // First stop (depot)
      const depotStart = routeStops[0];
      const depotStartMarker = createCustomMarker(
        [depotStart.latitude, depotStart.longitude],
        "D",
        "depot-marker"
      );
      depotStartMarker.addTo(map);
      markers.push(depotStartMarker);

      // Last stop (depot)
      const depotEnd = routeStops[routeStops.length - 1];
      const depotEndMarker = createCustomMarker(
        [depotEnd.latitude, depotEnd.longitude],
        "D",
        "depot-marker"
      );
      depotEndMarker.addTo(map);
      markers.push(depotEndMarker);
    }

    // Add delivery stop markers
    deliveryStops.forEach((stop) => {
      let markerClass = "pending-marker";

      if (stop.id == activeStopId) {
        markerClass = "active-marker";
      } else if (stop.status === "completed") {
        markerClass = "completed-marker";
      } else if (stop.status === "failed") {
        markerClass = "failed-marker";
      }

      const marker = createCustomMarker(
        [stop.latitude, stop.longitude],
        stop.stop_number,
        markerClass
      );

      marker.bindPopup(`
                <strong>${stop.location_name}</strong><br>
                ${stop.location_address}<br>
                <small>Stop #${stop.stop_number}</small>
                ${
                  stop.time_window_start
                    ? `<br><small>Time window: ${formatTimeWindow(
                        stop.time_window_start,
                        stop.time_window_end
                      )}</small>`
                    : ""
                }
            `);

      marker.on("click", () => {
        setActiveStop(stop.id);
      });

      marker.addTo(map);
      markers.push(marker);
    });

    // Fit bounds to show all markers
    const allCoordinates = markers.map((marker) => marker.getLatLng());
    if (allCoordinates.length > 0) {
      map.fitBounds(L.latLngBounds(allCoordinates).pad(0.2));
    }
  }

  // Function to set active stop
  function setActiveStop(stopId) {
    // Update active stop ID
    activeStopId = stopId;

    // Update stop cards
    const stopCards = document.querySelectorAll(".stop-card");
    stopCards.forEach((card) => {
      card.classList.remove("active");
      if (card.dataset.stopId == stopId) {
        card.classList.add("active");
        // Scroll to the card
        card.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });

    // Update markers
    updateMarkers();

    // Find stop data
    const stop = deliveryStops.find((s) => s.id == stopId);
    if (stop) {
      // Center map on stop
      map.setView([stop.latitude, stop.longitude], 15);

      // Show directions if we have current location
      if (currentLocation) {
        showDirectionsToStop(stop);
      }
    }
  }

  // Function to update markers when active stop changes
  function updateMarkers() {
    markers.forEach((marker) => map.removeLayer(marker));
    addRouteMarkers();
  }

  // Function to navigate to a stop
  function navigateToStop(stop) {
    if (!currentLocation) {
      showToast("Waiting for your location...", "warning");
      requestLocationPermission();
      return;
    }

    // Set as active stop
    setActiveStop(stop.id);

    // Show directions
    showDirectionsToStop(stop);

    // Switch to directions tab
    const directionsTab = document.getElementById("directions-tab");
    directionsTab.click();
  }

  // Function to show directions to a stop
  function showDirectionsToStop(stop) {
    // Remove existing routing control
    if (routingControl) {
      map.removeControl(routingControl);
    }

    // Create new routing control
    routingControl = L.Routing.control({
      waypoints: [
        L.latLng(currentLocation.lat, currentLocation.lng),
        L.latLng(stop.latitude, stop.longitude),
      ],
      routeWhileDragging: false,
      showAlternatives: false,
      fitSelectedRoutes: false,
      show: false, // Don't show the default instructions view
      lineOptions: {
        styles: [
          { color: "#3498db", opacity: 0.8, weight: 6 },
          { color: "white", opacity: 0.3, weight: 4 },
        ],
      },
      createMarker: () => {
        return null;
      }, // Don't create default markers
    }).addTo(map);

    // Handle route calculation
    routingControl.on("routesfound", function (e) {
      const routes = e.routes;
      const route = routes[0]; // Get the first route

      // Display turn-by-turn directions
      displayDirections(route);

      // Fit map to show the route
      const bounds = L.latLngBounds(route.coordinates);
      map.fitBounds(bounds.pad(0.1));
    });
  }

  // Function to display turn-by-turn directions
  function displayDirections(route) {
    const directionsContainer = document.getElementById("direction-steps");
    directionsContainer.innerHTML = "";

    if (!route.instructions || route.instructions.length === 0) {
      directionsContainer.innerHTML = `
                <div class="text-center py-3">
                    <p>No directions available for this route.</p>
                </div>
            `;
      return;
    }

    // Create header with distance and time
    const header = document.createElement("div");
    header.className = "direction-header p-2 bg-light";
    header.innerHTML = `
            <strong>Total Distance:</strong> ${(
              route.summary.totalDistance / 1000
            ).toFixed(1)} km
            <strong class="ms-3">Estimated Time:</strong> ${formatDuration(
              route.summary.totalTime
            )}
        `;
    directionsContainer.appendChild(header);

    // Add each instruction
    route.instructions.forEach((instruction, index) => {
      const step = document.createElement("div");
      step.className = "direction-step";

      // Get appropriate icon for instruction
      let icon = "arrow-right";
      if (instruction.type === "Straight") {
        icon = "arrow-up";
      } else if (instruction.type === "SlightRight") {
        icon = "arrow-up-right";
      } else if (instruction.type === "Right") {
        icon = "arrow-right";
      } else if (instruction.type === "SharpRight") {
        icon = "arrow-right";
      } else if (instruction.type === "SlightLeft") {
        icon = "arrow-up-left";
      } else if (instruction.type === "Left") {
        icon = "arrow-left";
      } else if (instruction.type === "SharpLeft") {
        icon = "arrow-left";
      } else if (instruction.type === "DestinationReached") {
        icon = "flag-checkered";
      } else if (instruction.type === "Roundabout") {
        icon = "sync";
      } else if (instruction.type === "StartAt") {
        icon = "play";
      }

      // Create step content
      step.innerHTML = `
                <i class="fas fa-${icon}"></i>
                <span>${instruction.text}</span>
                <small class="text-muted float-end">${(
                  instruction.distance / 1000
                ).toFixed(1)} km</small>
            `;

      directionsContainer.appendChild(step);

      // Highlight the next maneuver
      if (index === 1) {
        step.classList.add("highlighted");
      }
    });
  }

  // Function to request location permission
  function requestLocationPermission() {
    if ("geolocation" in navigator) {
      // Check if already watching position
      if (watchId) {
        return;
      }

      // Show permission modal on first request
      if (!localStorage.getItem("locationPermissionRequested")) {
        const modal = new bootstrap.Modal(
          document.getElementById("locationPermissionModal")
        );
        modal.show();

        document
          .getElementById("enable-location-btn")
          .addEventListener("click", () => {
            modal.hide();
            startLocationTracking();
            localStorage.setItem("locationPermissionRequested", "true");
          });
      } else {
        startLocationTracking();
      }
    } else {
      showToast("Geolocation is not supported by your browser", "danger");
    }
  }

  // Function to start location tracking
  function startLocationTracking() {
    watchId = navigator.geolocation.watchPosition(
      // Success callback
      (position) => {
        const { latitude, longitude } = position.coords;

        // Update current location
        currentLocation = {
          lat: latitude,
          lng: longitude,
        };

        // Update current location marker
        updateCurrentLocationMarker();

        // If there's an active stop and routing control, update the route
        if (activeStopId && routingControl) {
          const stop = deliveryStops.find((s) => s.id == activeStopId);
          if (stop) {
            routingControl.setWaypoints([
              L.latLng(currentLocation.lat, currentLocation.lng),
              L.latLng(stop.latitude, stop.longitude),
            ]);
          }
        }
      },
      // Error callback
      (error) => {
        console.error("Geolocation error:", error);
        showToast("Unable to access your location", "danger");
      },
      // Options
      {
        enableHighAccuracy: true,
        maximumAge: 0,
        timeout: 5000,
      }
    );
  }

  // Function to update current location marker
  function updateCurrentLocationMarker() {
    // Remove old marker if exists
    const oldMarker = markers.find((marker) => marker.isCurrentLocation);
    if (oldMarker) {
      map.removeLayer(oldMarker);
      markers = markers.filter((marker) => marker !== oldMarker);
    }

    // Create new marker
    if (currentLocation) {
      const locationMarker = L.circleMarker(
        [currentLocation.lat, currentLocation.lng],
        {
          radius: 8,
          fillColor: "#3498db",
          color: "#fff",
          weight: 2,
          opacity: 1,
          fillOpacity: 1,
        }
      );

      // Add custom property to identify this marker
      locationMarker.isCurrentLocation = true;

      locationMarker.addTo(map);
      markers.push(locationMarker);
    }
  }

  // Function to center map on current location
  function centerOnCurrentLocation() {
    if (currentLocation) {
      map.setView([currentLocation.lat, currentLocation.lng], 16);
    } else {
      showToast("Waiting for your location...", "warning");
      requestLocationPermission();
    }
  }

  // Function to mark a stop as arrived
  function markStopAsArrived(stopId) {
    fetch(`/driver/stops/${stopId}/status`, {
      method: "PUT",
      headers: {
        Authorization: "Bearer " + getToken(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: "arrived",
      }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to update stop status");
        }
        return response.json();
      })
      .then((data) => {
        // Update stop in local data
        const stopIndex = deliveryStops.findIndex((s) => s.id == stopId);
        if (stopIndex !== -1) {
          deliveryStops[stopIndex] = data.stop;
        }

        // Re-render stops
        renderStops();

        // Update markers
        updateMarkers();

        // Show success message
        showToast("Marked as arrived", "success");
      })
      .catch((error) => {
        console.error("Error updating stop status:", error);
        showToast("Failed to update stop status", "danger");
      });
  }

  // Function to open delivery action modal
  function openDeliveryActionModal(stopId) {
    // Find stop
    const stop = deliveryStops.find((s) => s.id == stopId);
    if (!stop) {
      return;
    }

    // Set modal title
    document.getElementById(
      "deliveryActionModalLabel"
    ).textContent = `Complete Delivery: ${stop.location_name}`;

    // Clear previous values
    document.getElementById("delivery-notes").value = "";
    document.getElementById("delivery-status").value = "completed";
    document.getElementById("delivery-photo").value = "";

    // Initialize signature pad
    const canvas = document.getElementById("signature-pad");
    signaturePad = new SignaturePad(canvas, {
      backgroundColor: "rgb(255, 255, 255)",
    });

    // Set up clear button
    document.getElementById("clear-signature").addEventListener("click", () => {
      signaturePad.clear();
    });

    // Set up submit button
    const submitBtn = document.getElementById("submit-delivery");
    submitBtn.dataset.stopId = stopId;

    // Remove previous event listeners
    const newSubmitBtn = submitBtn.cloneNode(true);
    submitBtn.parentNode.replaceChild(newSubmitBtn, submitBtn);

    // Add event listener
    newSubmitBtn.addEventListener("click", completeDelivery);

    // Show modal
    const modal = new bootstrap.Modal(
      document.getElementById("deliveryActionModal")
    );
    modal.show();
  }

  // Function to complete delivery
  function completeDelivery(e) {
    const stopId = e.target.dataset.stopId;
    const status = document.getElementById("delivery-status").value;
    const notes = document.getElementById("delivery-notes").value;

    // Validate form
    if (status === "completed" && signaturePad.isEmpty()) {
      showToast("Please provide a signature", "warning");
      return;
    }

    // Disable submit button
    e.target.disabled = true;
    e.target.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';

    // Prepare form data
    const formData = new FormData();
    formData.append("status", status);
    formData.append("notes", notes);

    // Add signature if provided
    if (!signaturePad.isEmpty()) {
      const signatureData = signaturePad.toDataURL();
      const blobBin = atob(signatureData.split(",")[1]);
      const array = [];
      for (let i = 0; i < blobBin.length; i++) {
        array.push(blobBin.charCodeAt(i));
      }
      const signatureBlob = new Blob([new Uint8Array(array)], {
        type: "image/png",
      });
      formData.append("signature", signatureBlob, "signature.png");
    }

    // Add photo if provided
    const photoInput = document.getElementById("delivery-photo");
    if (photoInput.files.length > 0) {
      formData.append("photo", photoInput.files[0]);
    }

    // Submit form
    fetch(`/driver/stops/${stopId}/proof`, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + getToken(),
      },
      body: formData,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to upload delivery proof");
        }
        return response.json();
      })
      .then(() => {
        // Update stop status
        return fetch(`/driver/stops/${stopId}/status`, {
          method: "PUT",
          headers: {
            Authorization: "Bearer " + getToken(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            status: status,
            notes: notes,
          }),
        });
      })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to update stop status");
        }
        return response.json();
      })
      .then((data) => {
        // Hide modal
        bootstrap.Modal.getInstance(
          document.getElementById("deliveryActionModal")
        ).hide();

        // Update stop in local data
        const stopIndex = deliveryStops.findIndex((s) => s.id == stopId);
        if (stopIndex !== -1) {
          deliveryStops[stopIndex] = data.stop;
        }

        // Re-render stops
        renderStops();

        // Update markers
        updateMarkers();

        // Update active stop to the next pending stop
        const nextStop = deliveryStops.find(
          (stop) => stop.status === "pending"
        );
        if (nextStop) {
          setActiveStop(nextStop.id);
        }

        // Update route info
        updateRouteInfo();

        // Show success message
        showToast(`Delivery ${status}`, "success");

        // Check if all stops are completed
        const allCompleted = deliveryStops.every(
          (stop) => stop.status === "completed" || stop.status === "failed"
        );
        if (allCompleted) {
          showToast("All deliveries completed!", "success");

          // Ask if they want to complete the route
          if (
            confirm(
              "All deliveries are completed. Do you want to mark the route as completed?"
            )
          ) {
            completeRoute();
          }
        }
      })
      .catch((error) => {
        console.error("Error completing delivery:", error);
        showToast("Failed to complete delivery", "danger");

        // Re-enable submit button
        e.target.disabled = false;
        e.target.innerHTML = "Submit";
      });
  }

  // Function to complete route
  // Function to complete route - Modified to work with the fuel form modal
  function completeRoute() {
    // Only directly complete the route if we're not showing the fuel form
    if (
      !document.getElementById("completeRouteModal").classList.contains("show")
    ) {
      // If the modal isn't showing, proceed with direct route completion
      updateRouteStatus("completed");
    }
    // If the modal is showing, the submitRouteCompletion button handler will handle the completion
  }

  // New function to update route status (extracted from previous completeRoute function)
  function updateRouteStatus(status) {
    fetch(`/driver/routes/${routeId}/status`, {
      method: "PUT",
      headers: {
        Authorization: "Bearer " + getToken(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: status,
      }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to complete route");
        }
        return response.json();
      })
      .then((data) => {
        // Update route data
        routeData.driver_route = data.driver_route;

        // Update UI
        updateRouteInfo();

        // Show success message
        showToast("Route completed successfully", "success");

        // Redirect to dashboard after a delay
        setTimeout(() => {
          window.location.href = "/driver/dashboard";
        }, 2000);
      })
      .catch((error) => {
        console.error("Error completing route:", error);
        showToast("Failed to complete route", "danger");
      });
  }

  // Function to create custom marker
  function createCustomMarker(latlng, text, className) {
    const icon = L.divIcon({
      html: `<div class="stop-marker ${className}">${text}</div>`,
      className: "",
      iconSize: [30, 30],
    });

    return L.marker(latlng, { icon });
  }

  // Function to format time window
  function formatTimeWindow(start, end) {
    // Format to 12-hour time (e.g., 9:00 AM - 5:00 PM)
    const startTime = parseTimeString(start);
    const endTime = parseTimeString(end);

    if (!startTime || !endTime) {
      return "";
    }

    return `${formatTime(startTime)} - ${formatTime(endTime)}`;
  }

  // Function to parse time string (HH:MM) to Date object
  function parseTimeString(timeStr) {
    if (!timeStr) return null;

    const [hours, minutes] = timeStr.split(":").map(Number);
    const date = new Date();
    date.setHours(hours, minutes, 0, 0);
    return date;
  }

  // Function to format Date object to 12-hour time (e.g., 9:00 AM)
  function formatTime(date) {
    if (!date) return "";

    const hours = date.getHours();
    const minutes = date.getMinutes();
    const ampm = hours >= 12 ? "PM" : "AM";
    const formattedHours = hours % 12 || 12;
    const formattedMinutes = minutes.toString().padStart(2, "0");

    return `${formattedHours}:${formattedMinutes} ${ampm}`;
  }

  // Function to format duration in seconds to human-readable format
  function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0) {
      return `${hours} hr ${minutes} min`;
    } else {
      return `${minutes} min`;
    }
  }

  // Helper function to capitalize first letter
  function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
  }

  // Function to get token from localStorage
  function getToken() {
    return localStorage.getItem("driver_token") || "";
  }

  // Show toast notification
  function showToast(message, type = "info") {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById("toast-container");
    if (!toastContainer) {
      toastContainer = document.createElement("div");
      toastContainer.id = "toast-container";
      toastContainer.className =
        "toast-container position-fixed bottom-0 end-0 p-3";
      document.body.appendChild(toastContainer);
    }

    // Create toast
    const toastId = "toast-" + Date.now();
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.id = toastId;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    toast.setAttribute("aria-atomic", "true");

    // Toast content
    toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

    // Add to container
    toastContainer.appendChild(toast);

    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, {
      autohide: true,
      delay: 3000,
    });
    bsToast.show();
  }

  // Handle panel toggle
  function setupPanelToggle() {
    const panel = document.querySelector(".bottom-panel");
    const toggle = document.getElementById("panel-toggle");

    toggle.addEventListener("click", () => {
      panel.classList.toggle("minimized");
    });
  }

  // Handle refresh button
  function setupRefreshButton() {
    document
      .getElementById("refresh-route-btn")
      .addEventListener("click", () => {
        loadRouteData();
        showToast("Route data refreshed", "info");
      });
  }

  // Handle complete route button

  function setupCompleteRouteButton() {
    const completeRouteBtn = document.getElementById("complete-route-btn");

    if (completeRouteBtn) {
      completeRouteBtn.addEventListener("click", () => {
        // Check if all stops are completed
        const pendingStops = deliveryStops.filter(
          (stop) => stop.status === "pending" || stop.status === "arrived"
        );

        if (pendingStops.length > 0) {
          if (
            !confirm(
              `There are still ${pendingStops.length} uncompleted stops. Are you sure you want to complete the route?`
            )
          ) {
            return;
          }
        }

        // Instead of directly completing the route, show the fuel form modal
        // The modal's submit button will handle the actual completion
        const modal = new bootstrap.Modal(
          document.getElementById("completeRouteModal")
        );
        modal.show();
      });
    } else {
      console.warn("Complete route button not found in the DOM");
    }
  }

  // Resize handler for signature pad
  function resizeSignaturePad() {
    window.addEventListener("resize", () => {
      if (signaturePad) {
        const canvas = document.getElementById("signature-pad");
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext("2d").scale(ratio, ratio);
        signaturePad.clear(); // Clear and re-render
      }
    });
  }

  // Clean up resources when leaving the page
  function setupBeforeUnload() {
    window.addEventListener("beforeunload", () => {
      // Stop watching position
      if (watchId) {
        navigator.geolocation.clearWatch(watchId);
      }
    });
  }

  // Initialize emergency button functionality
  function initEmergencyFeatures() {
    // Get current pending stops count
    updatePendingStopsCount();

    // Set up emergency form handler
    document
      .getElementById("submitEmergency")
      .addEventListener("click", reportEmergency);

    // Set up cancel help request button
    document
      .getElementById("cancelHelpRequest")
      .addEventListener("click", cancelHelpRequest);

    // Start checking for assistance notifications
    checkForAssistanceRequests();

    // Check if we already have an active incident
    checkActiveIncidents();
  }

  // Count pending stops
  function updatePendingStopsCount() {
    pendingStops = deliveryStops.filter(
      (stop) => stop.status === "pending" || stop.status === "arrived"
    );

    const pendingCount = pendingStops.length;
    document.getElementById("pendingStopsCount").textContent = pendingCount;

    if (pendingCount > 0) {
      document.getElementById("pendingStopsInfo").classList.remove("d-none");
    } else {
      document.getElementById("pendingStopsInfo").classList.add("d-none");
    }
  }

  // Report emergency and request help
  function reportEmergency() {
    // Get form data
    const incidentType = document.getElementById("incidentType").value;
    const description = document.getElementById("incidentDescription").value;

    if (!incidentType) {
      showToast("Please select an issue type", "warning");
      return;
    }

    // Get location
    if (!currentLocation) {
      showToast("Waiting for your location...", "warning");
      requestLocationPermission();
      return;
    }

    // Disable submit button
    const submitBtn = document.getElementById("submitEmergency");
    submitBtn.disabled = true;
    submitBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Submitting...';

    // Create request data
    const requestData = {
      driver_route_id: routeId,
      incident_type: incidentType,
      description: description,
      location_lat: currentLocation.lat,
      location_lng: currentLocation.lng,
      location_address: getCurrentAddressFromMap() || "Unknown location",
    };

    // Submit request
    fetch("/api/driver/incidents", {
      method: "POST",
      headers: {
        Authorization: "Bearer " + getToken(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestData),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to report incident");
        }
        return response.json();
      })
      .then((data) => {
        // Store active incident
        activeIncident = data.incident;

        // Hide emergency modal
        const emergencyModal = bootstrap.Modal.getInstance(
          document.getElementById("emergencyModal")
        );
        emergencyModal.hide();

        // Show help status modal
        const helpStatusModal = new bootstrap.Modal(
          document.getElementById("helpStatusModal")
        );
        helpStatusModal.show();

        // Reset form
        document.getElementById("emergencyForm").reset();

        // Start checking for help status
        startCheckingHelpStatus();

        // Show success message
        showToast("Your request for assistance has been sent", "success");
      })
      .catch((error) => {
        console.error("Error reporting emergency:", error);
        showToast("Failed to send assistance request", "danger");

        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.innerHTML =
          '<i class="fas fa-paper-plane me-1"></i>Report & Request Help';
      });
  }

  // Cancel help request
  function cancelHelpRequest() {
    if (!activeIncident) {
      return;
    }

    // Confirm cancellation
    if (
      !confirm("Are you sure you want to cancel your request for assistance?")
    ) {
      return;
    }

    // Disable cancel button
    const cancelBtn = document.getElementById("cancelHelpRequest");
    cancelBtn.disabled = true;
    cancelBtn.textContent = "Cancelling...";

    // Cancel the incident
    fetch(`/api/driver/incidents/${activeIncident.id}/cancel`, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + getToken(),
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to cancel incident");
        }
        return response.json();
      })
      .then((data) => {
        // Reset active incident
        activeIncident = null;

        // Stop checking for help status
        stopCheckingHelpStatus();

        // Hide help status modal
        const helpStatusModal = bootstrap.Modal.getInstance(
          document.getElementById("helpStatusModal")
        );
        helpStatusModal.hide();

        // Show success message
        showToast("Assistance request cancelled", "info");
      })
      .catch((error) => {
        console.error("Error cancelling help request:", error);
        showToast("Failed to cancel assistance request", "danger");

        // Re-enable cancel button
        cancelBtn.disabled = false;
        cancelBtn.textContent = "Cancel Request";
      });
  }

  // Check active incidents
  function checkActiveIncidents() {
    fetch("/api/driver/incidents/active", {
      headers: {
        Authorization: "Bearer " + getToken(),
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to fetch active incidents");
        }
        return response.json();
      })
      .then((data) => {
        if (data && data.length > 0) {
          // We have an active incident
          activeIncident = data[0];

          // Show help status modal
          updateHelpStatusUI();

          // Start checking for help status
          startCheckingHelpStatus();
        }
      })
      .catch((error) => {
        console.error("Error checking active incidents:", error);
      });
  }

  // Start checking for help status
  function startCheckingHelpStatus() {
    if (incidentCheckInterval) {
      clearInterval(incidentCheckInterval);
    }

    // Check immediately
    updateHelpStatusUI();

    // Then check every 10 seconds
    incidentCheckInterval = setInterval(() => {
      if (activeIncident) {
        checkActiveIncidents();
      } else {
        stopCheckingHelpStatus();
      }
    }, 10000);
  }

  // Stop checking for help status
  function stopCheckingHelpStatus() {
    if (incidentCheckInterval) {
      clearInterval(incidentCheckInterval);
      incidentCheckInterval = null;
    }
  }

  // Update help status UI
  function updateHelpStatusUI() {
    if (!activeIncident) {
      return;
    }

    const waitingEl = document.getElementById("waitingForHelp");
    const assignedEl = document.getElementById("helpAssigned");
    const noHelpEl = document.getElementById("noHelpAvailable");

    // Hide all sections first
    waitingEl.classList.add("d-none");
    assignedEl.classList.add("d-none");
    noHelpEl.classList.add("d-none");

    // Show appropriate section
    if (
      activeIncident.help_status === "accepted" &&
      activeIncident.helper_info
    ) {
      // Help assigned
      assignedEl.classList.remove("d-none");

      // Update helper info
      document.getElementById("helperDriverName").textContent =
        activeIncident.helper_info.driver_name;
      document.getElementById("helperVehicleInfo").textContent =
        activeIncident.helper_info.vehicle || "Vehicle info not available";
      document.getElementById("helperAssignedTime").textContent =
        "Assigned at " + formatDateTime(activeIncident.helper_info.accepted_at);
      document.getElementById("transferredStopsCount").textContent =
        activeIncident.helper_info.stops_count;

      // Show help status modal if not already visible
      const helpStatusModal = new bootstrap.Modal(
        document.getElementById("helpStatusModal")
      );
      helpStatusModal.show();
    } else if (activeIncident.status === "reported") {
      // Still waiting
      waitingEl.classList.remove("d-none");
    } else {
      // No help available
      noHelpEl.classList.remove("d-none");
    }
  }

  // Check for assistance requests (for drivers who can help)
  function checkForAssistanceRequests() {
    // Only check if we're not the one requesting help
    if (activeIncident) {
      return;
    }

    fetch("/api/driver/assistance-requests", {
      headers: {
        Authorization: "Bearer " + getToken(),
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to fetch assistance requests");
        }
        return response.json();
      })
      .then((data) => {
        if (data && data.length > 0) {
          // We have assistance requests
          showAssistanceRequests(data);
        }
      })
      .catch((error) => {
        console.error("Error checking assistance requests:", error);
      });

    // Check again in 30 seconds
    setTimeout(checkForAssistanceRequests, 30000);
  }

  // Show assistance requests
  function showAssistanceRequests(requests) {
    // Add a notification badge to the header
    const headerEl = document.querySelector(".route-header");

    // Check if we already have a notification badge
    let badgeEl = headerEl.querySelector(".assistance-badge");

    if (!badgeEl) {
      // Create new badge
      badgeEl = document.createElement("div");
      badgeEl.className = "assistance-badge";
      badgeEl.innerHTML = `
            <button class="btn btn-warning btn-sm position-fixed top-0 end-0 m-2" data-bs-toggle="modal" data-bs-target="#assistanceRequestsModal">
                <i class="fas fa-exclamation-triangle me-1"></i>
                Drivers Need Help (<span class="assistance-count">${requests.length}</span>)
            </button>
        `;
      headerEl.appendChild(badgeEl);

      // Create the modal if it doesn't exist
      if (!document.getElementById("assistanceRequestsModal")) {
        const modalEl = document.createElement("div");
        modalEl.className = "modal fade";
        modalEl.id = "assistanceRequestsModal";
        modalEl.setAttribute("tabindex", "-1");
        modalEl.setAttribute("aria-labelledby", "assistanceRequestsModalLabel");
        modalEl.setAttribute("aria-hidden", "true");

        modalEl.innerHTML = `
                <div class="modal-dialog modal-dialog-centered modal-lg">
                    <div class="modal-content">
                        <div class="modal-header bg-warning text-dark">
                            <h5 class="modal-title" id="assistanceRequestsModalLabel">
                                <i class="fas fa-exclamation-triangle me-2"></i>Drivers Needing Help
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div id="assistance-requests-container">
                                <!-- Request cards will be inserted here -->
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            `;

        document.body.appendChild(modalEl);
      }
    } else {
      // Update existing badge count
      badgeEl.querySelector(".assistance-count").textContent = requests.length;
    }

    // Update modal content
    const requestsContainer = document.getElementById(
      "assistance-requests-container"
    );
    requestsContainer.innerHTML = "";

    requests.forEach((request) => {
      const template = document.getElementById("assistance-request-template");
      const card = document
        .importNode(template.content, true)
        .querySelector(".card");

      // Set data attributes
      card.dataset.transferId = request.id;

      // Set content
      card.querySelector(".driver-name").textContent =
        request.original_driver.name;
      card.querySelector(
        ".stops-count"
      ).textContent = `${request.stop_count} stops`;

      // Get incident type text
      const incidentType = request.incident.incident_type.replace("_", " ");
      card.querySelector(".incident-type").textContent =
        incidentType.charAt(0).toUpperCase() + incidentType.slice(1);

      // Set location and distance
      const locationText =
        request.incident.location.address ||
        `${request.incident.location.lat.toFixed(
          6
        )}, ${request.incident.location.lng.toFixed(6)}`;
      card.querySelector(".incident-location").textContent = locationText;

      if (request.distance_km) {
        card.querySelector(
          ".incident-distance"
        ).textContent = `${request.distance_km.toFixed(1)} km away`;
      } else {
        card.querySelector(".incident-distance").textContent =
          "Distance unknown";
      }

      // Set up button handlers
      card.querySelector(".view-on-map-btn").addEventListener("click", () => {
        // Close modal
        bootstrap.Modal.getInstance(
          document.getElementById("assistanceRequestsModal")
        ).hide();

        // Center map on incident location
        map.setView(
          [request.incident.location.lat, request.incident.location.lng],
          15
        );

        // Add a marker
        const marker = L.marker(
          [request.incident.location.lat, request.incident.location.lng],
          {
            icon: L.divIcon({
              html: '<div class="emergency-marker"><i class="fas fa-exclamation-triangle"></i></div>',
              className: "",
              iconSize: [40, 40],
            }),
          }
        ).addTo(map);

        // Add to markers array
        markers.push(marker);

        // Show popup
        marker
          .bindPopup(
            `
                <strong>${request.original_driver.name} needs help</strong><br>
                ${
                  incidentType.charAt(0).toUpperCase() + incidentType.slice(1)
                }<br>
                ${request.stop_count} stops remaining
            `
          )
          .openPopup();
      });

      card
        .querySelector(".accept-assistance-btn")
        .addEventListener("click", () => {
          acceptAssistanceRequest(request.id);
        });

      requestsContainer.appendChild(card);
    });
  }

  // Accept an assistance request
  function acceptAssistanceRequest(transferId) {
    // Confirm acceptance
    if (
      !confirm(
        "Are you sure you want to help with this route? This will add additional stops to your current route."
      )
    ) {
      return;
    }

    // Get button and disable it
    const acceptBtn = document.querySelector(
      `.assistance-card[data-transfer-id="${transferId}"] .accept-assistance-btn`
    );
    acceptBtn.disabled = true;
    acceptBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Accepting...';

    // Accept the transfer
    fetch(`/api/driver/transfers/${transferId}/accept`, {
      method: "POST",
      headers: {
        Authorization: "Bearer " + getToken(),
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to accept transfer");
        }
        return response.json();
      })
      .then((data) => {
        // Hide modal
        bootstrap.Modal.getInstance(
          document.getElementById("assistanceRequestsModal")
        ).hide();

        // Update UI to reflect new stops
        showToast(
          `You've accepted ${data.transfer.stop_count} additional stops. Refreshing route data...`,
          "success"
        );

        // Reload route data to get new stops
        setTimeout(() => {
          loadRouteData();
        }, 1500);
      })
      .catch((error) => {
        console.error("Error accepting assistance request:", error);
        showToast("Failed to accept assistance request", "danger");

        // Re-enable button
        acceptBtn.disabled = false;
        acceptBtn.innerHTML = '<i class="fas fa-check me-1"></i>I Can Help';
      });
  }

  // Helper function to get current address from map
  function getCurrentAddressFromMap() {
    return ""; // In a real system, you'd use reverse geocoding
  }

  // Helper function to format date/time
  function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) {
      return "";
    }

    const date = new Date(dateTimeStr);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // Initialize components
  function init() {
    // Initialize map
    initMap();

    // Setup UI event handlers
    setupPanelToggle();
    setupRefreshButton();
    setupCompleteRouteButton();
    resizeSignaturePad();
    setupBeforeUnload();

    // Initialize emergency features
    initEmergencyFeatures();
  }

  // Start initialization when DOM is loaded
  init();
});
