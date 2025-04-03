// Main JavaScript for Route Optimizer

// Show loading spinner during form submissions
document.addEventListener("DOMContentLoaded", function () {
  // Initialize loading spinner
  const body = document.querySelector("body");
  const loadingSpinner = document.createElement("div");
  loadingSpinner.className = "loading-spinner d-none";
  loadingSpinner.id = "loading-spinner";
  body.appendChild(loadingSpinner);
  // Check for active incidents
  checkForActiveIncidents();

  // Check for notifications
  checkForNotifications();

  // Add overlay for spinner
  const overlay = document.createElement("div");
  overlay.className = "d-none";
  overlay.id = "loading-overlay";
  overlay.style.position = "fixed";
  overlay.style.top = "0";
  overlay.style.left = "0";
  overlay.style.width = "100%";
  overlay.style.height = "100%";
  overlay.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
  overlay.style.zIndex = "1050";
  overlay.style.display = "flex";
  overlay.style.justifyContent = "center";
  overlay.style.alignItems = "center";
  overlay.appendChild(loadingSpinner);
  body.appendChild(overlay);

  // Show spinner on form submit
  const forms = document.querySelectorAll("form");
  forms.forEach((form) => {
    form.addEventListener("submit", function () {
      // Don't show spinner for small forms
      if (this.querySelectorAll("input, select").length > 1) {
        document.getElementById("loading-overlay").classList.remove("d-none");
        document.getElementById("loading-spinner").classList.remove("d-none");
      }
    });
  });

  // Initialize tooltips
  if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach((tooltip) => {
      new bootstrap.Tooltip(tooltip);
    });
  }
});

// Toast notification system
function showToast(message, type = "info") {
  // Create toast container if it doesn't exist
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
    document.body.appendChild(toastContainer);
  }

  // Create toast element
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

  // Initialize and show the toast
  const bsToast = new bootstrap.Toast(toast, {
    autohide: true,
    delay: 5000,
  });
  bsToast.show();

  // Remove toast from DOM after it's hidden
  toast.addEventListener("hidden.bs.toast", function () {
    this.remove();
  });
}

// Function to validate form inputs
function validateForm(formId) {
  const form = document.getElementById(formId);
  if (!form) return true;

  let isValid = true;

  // Check each required input
  const requiredInputs = form.querySelectorAll("[required]");
  requiredInputs.forEach((input) => {
    if (!input.value) {
      input.classList.add("is-invalid");
      isValid = false;
    } else {
      input.classList.remove("is-invalid");
    }
  });

  // Check time window validity
  const startTime = form.querySelector('[name="time_window_start"]');
  const endTime = form.querySelector('[name="time_window_end"]');

  if (startTime && endTime && startTime.value && endTime.value) {
    if (startTime.value >= endTime.value) {
      endTime.classList.add("is-invalid");
      if (
        !endTime.nextElementSibling ||
        !endTime.nextElementSibling.classList.contains("invalid-feedback")
      ) {
        const feedback = document.createElement("div");
        feedback.className = "invalid-feedback";
        feedback.textContent = "End time must be after start time";
        endTime.parentNode.insertBefore(feedback, endTime.nextSibling);
      }
      isValid = false;
    } else {
      endTime.classList.remove("is-invalid");
    }
  }

  return isValid;
}

// CSV file validation
function validateCsvFile(fileInput) {
  const file = fileInput.files[0];
  if (!file) return false;

  // Check file extension
  const fileName = file.name;
  const fileExt = fileName.split(".").pop().toLowerCase();

  if (fileExt !== "csv") {
    showToast("Please select a CSV file", "danger");
    return false;
  }

  // File size validation (max 5MB)
  const maxSize = 5 * 1024 * 1024; // 5MB
  if (file.size > maxSize) {
    showToast("File size exceeds 5MB limit", "danger");
    return false;
  }

  return true;
}

// Address geocoding preview
function previewAddress() {
  const addressInput = document.getElementById("address");
  if (!addressInput || !addressInput.value) return;

  const address = addressInput.value;
  const previewContainer = document.getElementById("address-preview");

  if (!previewContainer) {
    // Create preview container if it doesn't exist
    const container = document.createElement("div");
    container.id = "address-preview";
    container.className = "mt-2 small";
    container.innerHTML =
      '<div class="spinner-border spinner-border-sm text-primary" role="status"></div> Validating address...';

    addressInput.parentNode.appendChild(container);
  } else {
    previewContainer.innerHTML =
      '<div class="spinner-border spinner-border-sm text-primary" role="status"></div> Validating address...';
  }

  // Simulate address validation (in a real app, this would call the backend API)
  setTimeout(() => {
    document.getElementById("address-preview").innerHTML =
      '<span class="text-success"><i class="fas fa-check-circle"></i> Address looks valid</span>';
  }, 1000);
}

// Dynamic form fields for time windows
function toggleTimeWindows(checkbox) {
  const timeWindowFields = document.getElementById("time-window-fields");
  if (!timeWindowFields) return;

  if (checkbox.checked) {
    timeWindowFields.classList.remove("d-none");
  } else {
    timeWindowFields.classList.add("d-none");
    // Clear values
    document.getElementById("time_window_start").value = "";
    document.getElementById("time_window_end").value = "";
  }
}

// Initialize map inputs if present
function initializeMapInputs() {
  const addressInputs = document.querySelectorAll('input[name="address"]');

  addressInputs.forEach((input) => {
    // Add event listener for address lookup
    input.addEventListener("blur", function () {
      if (this.value) {
        previewAddress();
      }
    });
  });
}

// Add event listener for initializing map inputs
document.addEventListener("DOMContentLoaded", initializeMapInputs);

// Function to export routes to different formats
function exportRoute(routeId, format) {
  const formats = {
    json: "/api/routes/",
    csv: "/api/routes/",
    pdf: "/api/routes/",
  };

  if (!formats[format]) {
    showToast("Unsupported export format", "danger");
    return;
  }

  const url = formats[format] + routeId + "?format=" + format;
  window.location.href = url;
}

// Function to simulate route animation on map
function animateRoute(map, routeLayer) {
  if (!map || !routeLayer) return;

  // Reset animation
  routeLayer.setStyle({
    dashArray: "",
    dashOffset: "",
  });

  // Apply animation
  routeLayer.setStyle({
    dashArray: "15, 10",
    lineCap: "round",
  });

  let dashOffset = 0;

  function animate() {
    dashOffset -= 2;
    routeLayer.setStyle({
      dashOffset: dashOffset,
    });

    requestAnimationFrame(animate);
  }

  animate();
}

// Function to prepare a sample CSV template for download
function downloadSampleCsv() {
  const csvContent =
    "name,address,time_window_start,time_window_end\n" +
    'Customer 1,"123 Main St, New York, NY",09:00,12:00\n' +
    'Customer 2,"456 Park Ave, New York, NY",13:00,17:00\n' +
    'Warehouse,"789 Broadway, New York, NY",08:00,18:00';

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", "sample_locations.csv");
  link.style.visibility = "hidden";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Check for active incidents and update notification bell
function checkForActiveIncidents() {
  fetch("/api/admin/incidents")
    .then((response) => response.json())
    .then((data) => {
      // Update incident count in navbar
      const incidentCount = data.counts.active;
      const incidentBadge = document.querySelector(".incident-count");

      if (incidentCount > 0) {
        incidentBadge.textContent = incidentCount;
        incidentBadge.classList.remove("d-none");

        // Add notification if we have new incidents
        if (
          incidentCount >
          parseInt(localStorage.getItem("lastIncidentCount") || 0)
        ) {
          addNotification(
            "New incident reported",
            "A driver has reported an incident and needs assistance.",
            "danger"
          );
        }

        // Store current count
        localStorage.setItem("lastIncidentCount", incidentCount);
      } else {
        incidentBadge.classList.add("d-none");
      }
    })
    .catch((error) => console.error("Error checking incidents:", error));

  // Check again in 60 seconds
  setTimeout(checkForActiveIncidents, 60000);
}

// Check for notifications (for drivers and admins)
function checkForNotifications() {
  fetch("/api/notifications")
    .then((response) => response.json())
    .then((data) => {
      if (data.notifications && data.notifications.length > 0) {
        // Update notification count
        const notificationCount = data.unread_count;
        const notificationBadge = document.querySelector(".notification-count");

        if (notificationCount > 0) {
          notificationBadge.textContent = notificationCount;
          notificationBadge.classList.remove("d-none");
        } else {
          notificationBadge.classList.add("d-none");
        }

        // Update notifications dropdown
        updateNotificationsDropdown(data.notifications);
      }
    })
    .catch((error) => console.error("Error checking notifications:", error));

  // Check again in 30 seconds
  setTimeout(checkForNotifications, 30000);
}

// Update notifications dropdown
function updateNotificationsDropdown(notifications) {
  const container = document.getElementById("notifications-container");

  // Clear existing items except header and divider
  while (container.childElementCount > 2) {
    container.removeChild(container.lastChild);
  }

  // Add notifications
  if (notifications.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.innerHTML = `
            <a class="dropdown-item text-center text-muted" href="#">
                No new notifications
            </a>
        `;
    container.appendChild(emptyItem);
  } else {
    notifications.forEach((notification) => {
      const item = document.createElement("li");

      // Determine notification class based on type
      let notificationClass = "";
      let icon = "info-circle";

      if (notification.notification_type.includes("assistance")) {
        notificationClass = "bg-warning text-dark";
        icon = "exclamation-triangle";
      } else if (notification.notification_type.includes("completed")) {
        notificationClass = "bg-success text-white";
        icon = "check-circle";
      } else if (notification.notification_type.includes("incident")) {
        notificationClass = "bg-danger text-white";
        icon = "exclamation-circle";
      }

      item.innerHTML = `
                <a class="dropdown-item ${
                  notification.is_read ? "text-muted" : ""
                }" href="#" data-notification-id="${notification.id}">
                    <div class="d-flex align-items-center">
                        <div class="flex-shrink-0 me-2">
                            <div class="notification-icon ${notificationClass}">
                                <i class="fas fa-${icon}"></i>
                            </div>
                        </div>
                        <div class="flex-grow-1">
                            <div>${notification.content}</div>
                            <small class="text-muted">${formatTimeAgo(
                              notification.created_at
                            )}</small>
                        </div>
                    </div>
                </a>
            `;

      // Add click handler to mark as read
      item.querySelector("a").addEventListener("click", function (e) {
        e.preventDefault();
        markNotificationAsRead(notification.id);

        // Handle specific notification types
        if (notification.notification_type === "assistance_needed") {
          window.location.href = "/admin/incidents";
        } else if (notification.notification_type === "assistance_assigned") {
          checkActiveIncidents();
        }
      });

      container.appendChild(item);
    });

    // Add "Mark all as read" button
    const markAllItem = document.createElement("li");
    markAllItem.innerHTML = `
            <div class="dropdown-item text-center">
                <button class="btn btn-sm btn-link" id="mark-all-read-btn">Mark all as read</button>
            </div>
        `;
    container.appendChild(markAllItem);

    // Add click handler
    markAllItem
      .querySelector("#mark-all-read-btn")
      .addEventListener("click", function (e) {
        e.preventDefault();
        markAllNotificationsAsRead();
      });
  }
}

// Mark notification as read
function markNotificationAsRead(notificationId) {
  fetch(`/api/notifications/${notificationId}/read`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      checkForNotifications();
    })
    .catch((error) =>
      console.error("Error marking notification as read:", error)
    );
}

// Mark all notifications as read
function markAllNotificationsAsRead() {
  fetch("/api/notifications/read-all", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      checkForNotifications();
    })
    .catch((error) =>
      console.error("Error marking all notifications as read:", error)
    );
}

// Add a notification manually (for testing)
function addNotification(title, message, type = "info") {
  // If we don't have the notifications container, create it
  let container = document.getElementById("notifications-container");
  if (!container) {
    return;
  }

  // Create new notification
  const notification = {
    id: Date.now(),
    content: title,
    notification_type: type,
    is_read: false,
    created_at: new Date().toISOString(),
  };

  // Add to UI
  const item = document.createElement("li");
  let notificationClass = "";
  let icon = "info-circle";

  if (type === "warning") {
    notificationClass = "bg-warning text-dark";
    icon = "exclamation-triangle";
  } else if (type === "success") {
    notificationClass = "bg-success text-white";
    icon = "check-circle";
  } else if (type === "danger") {
    notificationClass = "bg-danger text-white";
    icon = "exclamation-circle";
  }

  item.innerHTML = `
        <a class="dropdown-item" href="#" data-notification-id="${notification.id}">
            <div class="d-flex align-items-center">
                <div class="flex-shrink-0 me-2">
                    <div class="notification-icon ${notificationClass}">
                        <i class="fas fa-${icon}"></i>
                    </div>
                </div>
                <div class="flex-grow-1">
                    <div>${title}</div>
                    <small>${message}</small>
                    <small class="text-muted">Just now</small>
                </div>
            </div>
        </a>
    `;

  // Insert after divider
  container.insertBefore(item, container.childNodes[2]);

  // Update notification count
  const notificationBadge = document.querySelector(".notification-count");
  const currentCount = parseInt(notificationBadge.textContent || "0");
  notificationBadge.textContent = currentCount + 1;
  notificationBadge.classList.remove("d-none");

  // Show a toast if supported
  if (typeof bootstrap !== "undefined" && bootstrap.Toast) {
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
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    toast.setAttribute("aria-atomic", "true");

    toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong><br>${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

    toastContainer.appendChild(toast);

    const toastInstance = new bootstrap.Toast(toast);
    toastInstance.show();
  }
}

// Format time ago
function formatTimeAgo(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) {
    return "Just now";
  } else if (diff < 3600) {
    const minutes = Math.floor(diff / 60);
    return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
  } else if (diff < 86400) {
    const hours = Math.floor(diff / 3600);
    return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  } else {
    const days = Math.floor(diff / 86400);
    return `${days} day${days > 1 ? "s" : ""} ago`;
  }
}
