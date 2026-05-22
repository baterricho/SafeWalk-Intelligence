(function () {
    function csrfToken() {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) return decodeURIComponent(match[1]);
        const meta = document.querySelector("meta[name='csrf-token']");
        return meta ? meta.getAttribute("content") : "";
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function riskColor(risk) {
        return {
            low: "#16a34a",
            medium: "#eab308",
            high: "#f97316",
            critical: "#dc2626"
        }[risk] || "#2563eb";
    }

    function markerIcon(risk) {
        return L.divIcon({
            className: "",
            html: `<div class="marker-dot" style="background:${riskColor(risk)}"></div>`,
            iconSize: [18, 18],
            iconAnchor: [9, 9]
        });
    }

    function addBaseLayers(map) {
        const satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
            maxZoom: 20,
            maxNativeZoom: 17,
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
        });
        const streetMap = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            maxNativeZoom: 19,
            attribution: "&copy; OpenStreetMap contributors"
        });

        satellite.addTo(map);
        L.control.layers(
            {
                "Satellite": satellite,
                "Street Map": streetMap
            },
            null,
            { collapsed: false }
        ).addTo(map);

        return {
            satellite: satellite,
            streetMap: streetMap
        };
    }

    function prepareAutoFillInput(input) {
        if (!input || input.dataset.geocodeListenerAttached === "true") return;
        input.dataset.geocodeListenerAttached = "true";
        input.addEventListener("input", function () {
            input.dataset.geocodeAutofilled = "false";
        });
    }

    async function reverseGeocodeAndFill(lat, lng, inputId, statusId, options) {
        const input = document.getElementById(inputId);
        const status = document.getElementById(statusId);
        const settings = options || {};
        if (!input || !status) return false;
        prepareAutoFillInput(input);

        try {
            status.textContent = settings.loadingText || "Getting location name...";
            const response = await fetch(`/api/geocoding/reverse/?lat=${lat}&lng=${lng}`);
            const data = await response.json();
            const canAutofill = !input.value.trim() || input.dataset.geocodeAutofilled === "true";

            if (data.success) {
                if (canAutofill) {
                    input.value = data.short_name || data.display_name;
                    input.dataset.geocodeAutofilled = "true";
                }
                status.textContent = settings.successText || "Location pinned successfully.";
                status.classList.add("pinned");
                return true;
            }

            status.textContent = input.value.trim()
                ? (settings.successText || "Location pinned successfully.")
                : (settings.failureText || "Location pinned. Please type a landmark manually.");
            status.classList.toggle("pinned", Boolean(input.value.trim()));
            return false;
        } catch (error) {
            status.textContent = input.value.trim()
                ? (settings.successText || "Location pinned successfully.")
                : (settings.errorText || "Location pinned. Location name unavailable.");
            status.classList.toggle("pinned", Boolean(input.value.trim()));
            return false;
        }
    }

    window.reverseGeocodeAndFill = reverseGeocodeAndFill;

    window.SafeWalkDashboard = {
        init: function (config) {
            const dataNode = document.getElementById(config.dataElement);
            if (!dataNode || !window.L) return;
            const reports = JSON.parse(dataNode.textContent || "[]");
            const map = L.map(config.mapId).setView([9.7418, 118.7351], 15);
            addBaseLayers(map);

            const markerLayer = L.layerGroup().addTo(map);
            const heatmapLayer = L.heatLayer([], {
                radius: 25,
                blur: 15,
                maxZoom: 17,
                gradient: { 0.4: "blue", 0.6: "yellow", 0.8: "orange", 1.0: "red" }
            });

            let showHeatmap = false;

            const list = document.getElementById(config.listId);
            const count = document.getElementById(config.countId);
            const search = document.getElementById(config.searchId);
            const category = document.getElementById(config.categoryId);
            const risk = document.getElementById(config.riskId);
            const status = document.getElementById(config.statusId);
            const clear = document.getElementById(config.clearId);

            function filteredReports() {
                const q = (search.value || "").toLowerCase().trim();
                return reports.filter(function (report) {
                    const haystack = `${report.title} ${report.description} ${report.location_name}`.toLowerCase();
                    return (!q || haystack.includes(q))
                        && (!category.value || report.category === category.value)
                        && (!risk.value || report.risk_level === risk.value)
                        && (!status.value || report.status === status.value);
                });
            }

            function render() {
                const visible = filteredReports();
                markerLayer.clearLayers();
                heatmapLayer.setLatLngs([]);
                list.innerHTML = "";
                count.textContent = visible.length;
                const bounds = [];
                const heatPoints = [];

                visible.forEach(function (report) {
                    const latlng = [report.latitude, report.longitude];
                    bounds.push(latlng);
                    
                    // Assign intensity based on risk level
                    let intensity = 0.4;
                    if (report.risk_level === "medium") intensity = 0.6;
                    if (report.risk_level === "high") intensity = 0.8;
                    if (report.risk_level === "critical") intensity = 1.0;
                    heatPoints.push([report.latitude, report.longitude, intensity]);

                    L.marker(latlng, { icon: markerIcon(report.risk_level) })
                        .bindPopup(
                            `<strong>${escapeHtml(report.title)}</strong><br>` +
                            `<span>${escapeHtml(report.location_name)}</span><br>` +
                            `<a class="btn btn-sm btn-safewalk mt-2" href="${report.detail_url}">View Details</a>`
                        )
                        .addTo(markerLayer);

                    const item = document.createElement("article");
                    item.className = "report-card-v2";
                    item.innerHTML = `
                        <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
                            <strong class="title">${escapeHtml(report.title)}</strong>
                            <span class="risk-badge risk-${report.risk_level}">${escapeHtml(report.risk_display)}</span>
                        </div>
                        <div class="location mb-2">
                            <i class="bi bi-geo-alt-fill"></i> ${escapeHtml(report.location_name)}
                        </div>
                        <p class="description">${escapeHtml(report.description).slice(0, 150)}${report.description.length > 150 ? "..." : ""}</p>
                        <div class="d-flex justify-content-between align-items-center mt-3">
                            <div class="d-flex gap-2">
                                <span class="score-chip">${report.safety_score} / 100</span>
                                <span class="status-chip status-${report.status}">${escapeHtml(report.status_display)}</span>
                            </div>
                            <a class="btn btn-sm btn-outline-teal" href="${report.detail_url}">View Details</a>
                        </div>
                    `;
                    list.appendChild(item);
                });

                if (showHeatmap) {
                    heatmapLayer.setLatLngs(heatPoints);
                    if (!map.hasLayer(heatmapLayer)) heatmapLayer.addTo(map);
                    if (map.hasLayer(markerLayer)) map.removeLayer(markerLayer);
                } else {
                    if (map.hasLayer(heatmapLayer)) map.removeLayer(heatmapLayer);
                    if (!map.hasLayer(markerLayer)) markerLayer.addTo(map);
                }

                if (bounds.length) {
                    map.fitBounds(bounds, { padding: [35, 35], maxZoom: 17 });
                }
            }

            const toggleMarkersBtn = document.getElementById("toggle-markers-btn");
            const toggleHeatmapBtn = document.getElementById("toggle-heatmap-btn");

            if (toggleMarkersBtn && toggleHeatmapBtn) {
                toggleMarkersBtn.addEventListener("click", function () {
                    showHeatmap = false;
                    toggleMarkersBtn.classList.add("btn-teal-soft", "active");
                    toggleMarkersBtn.classList.remove("btn-outline-teal");
                    toggleHeatmapBtn.classList.remove("btn-teal-soft", "active");
                    toggleHeatmapBtn.classList.add("btn-outline-teal");
                    render();
                });

                toggleHeatmapBtn.addEventListener("click", function () {
                    showHeatmap = true;
                    toggleHeatmapBtn.classList.add("btn-teal-soft", "active");
                    toggleHeatmapBtn.classList.remove("btn-outline-teal");
                    toggleMarkersBtn.classList.remove("btn-teal-soft", "active");
                    toggleMarkersBtn.classList.add("btn-outline-teal");
                    render();
                });
            }

            [search, category, risk, status].forEach(function (input) {
                input.addEventListener("input", render);
                input.addEventListener("change", render);
            });

            // Filter chips logic
            const chips = document.querySelectorAll(".filter-chip");
            chips.forEach(function (chip) {
                chip.addEventListener("click", function () {
                    chips.forEach(c => c.classList.remove("active"));
                    chip.classList.add("active");

                    const filter = chip.dataset.filter;
                    // Reset filters first
                    category.value = "";
                    risk.value = "";
                    status.value = "";

                    if (filter === "critical") risk.value = "critical";
                    else if (filter === "high") risk.value = "high";
                    else if (filter === "resolved") status.value = "resolved";
                    else if (filter === "verified") status.value = "verified";
                    // Note: "nearby" would require geo logic, for now we just show all or leave as is

                    render();
                });
            });

            clear.addEventListener("click", function () {
                search.value = "";
                category.value = "";
                risk.value = "";
                status.value = "";
                chips.forEach(c => c.classList.remove("active"));
                const allChip = document.querySelector('[data-filter="all"]');
                if (allChip) allChip.classList.add("active");
                render();
            });

            setTimeout(function () {
                map.invalidateSize();
                render();
            }, 100);
        }
    };

    window.SafeWalkReportMap = {
        init: function (elementId) {
            const node = document.getElementById(elementId);
            if (!node || !window.L) return;
            const lat = parseFloat(node.dataset.lat);
            const lng = parseFloat(node.dataset.lng);
            const title = node.dataset.title || "Report location";
            const risk = node.dataset.risk || "Unknown risk";
            const riskKey = node.dataset.riskKey || "critical";
            const status = node.dataset.status || "Unknown status";
            const map = L.map(elementId).setView([lat, lng], 17);
            addBaseLayers(map);
            L.marker([lat, lng], { icon: markerIcon(riskKey) })
                .addTo(map)
                .bindPopup(`<strong>${escapeHtml(title)}</strong><br>Risk: ${escapeHtml(risk)}<br>Status: ${escapeHtml(status)}`)
                .openPopup();
            setTimeout(function () { map.invalidateSize(); }, 100);
        }
    };

    window.SafeWalkFormMaps = {
        initSinglePinMap: function (config) {
            const node = document.getElementById(config.mapId);
            if (!node || !window.L) return;
            const form = node.closest("form");
            const latInput = form.querySelector(`[name="${config.latitudeName}"]`);
            const lngInput = form.querySelector(`[name="${config.longitudeName}"]`);
            const status = document.getElementById(config.statusId);
            const currentButton = document.getElementById(config.currentButtonId);
            const errorBox = form.querySelector(".client-errors");
            const defaultCenter = [9.7786, 118.7353];
            const initialLat = parseFloat(latInput.value);
            const initialLng = parseFloat(lngInput.value);
            const hasInitialPin = !Number.isNaN(initialLat) && !Number.isNaN(initialLng);
            const map = L.map(config.mapId).setView(hasInitialPin ? [initialLat, initialLng] : defaultCenter, hasInitialPin ? 17 : 15);
            let marker = null;

            addBaseLayers(map);

            function setPin(lat, lng, zoom) {
                latInput.value = lat.toFixed(6);
                lngInput.value = lng.toFixed(6);
                if (marker) {
                    marker.setLatLng([lat, lng]);
                } else {
                    marker = L.marker([lat, lng], { icon: markerIcon("high") }).addTo(map);
                }
                map.setView([lat, lng], zoom || map.getZoom());
                status.textContent = config.pinnedText;
                status.classList.add("pinned");
                if (config.locationInputId) {
                    reverseGeocodeAndFill(
                        latInput.value,
                        lngInput.value,
                        config.locationInputId,
                        config.statusId,
                        {
                            successText: config.pinnedText,
                            failureText: "Location pinned. Please type a landmark manually.",
                            errorText: "Location pinned. Location name unavailable."
                        }
                    );
                }
            }

            if (hasInitialPin) {
                setPin(initialLat, initialLng, 17);
            }

            map.on("click", function (event) {
                setPin(event.latlng.lat, event.latlng.lng);
            });

            currentButton.addEventListener("click", function () {
                if (!navigator.geolocation) {
                    status.textContent = "Your browser does not support current location.";
                    return;
                }
                status.textContent = "Finding your current location...";
                navigator.geolocation.getCurrentPosition(
                    function (position) {
                        setPin(position.coords.latitude, position.coords.longitude, 17);
                    },
                    function () {
                        status.textContent = "Could not get your current location. You can still click the map.";
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            });

            form.addEventListener("submit", function (event) {
                if (!latInput.value || !lngInput.value) {
                    event.preventDefault();
                    status.textContent = config.missingText;
                    status.classList.remove("pinned");
                    if (errorBox) {
                        errorBox.classList.remove("d-none");
                        errorBox.innerHTML = escapeHtml(config.missingText);
                    }
                }
            });

            setTimeout(function () { map.invalidateSize(); }, 150);
        },

        initSavedRouteMap: function (config) {
            const node = document.getElementById(config.mapId);
            if (!node || !window.L) return;
            const form = node.closest("form");
            const status = document.getElementById(config.statusId);
            const startButton = document.getElementById(config.pinStartId);
            const endButton = document.getElementById(config.pinEndId);
            const currentStartButton = document.getElementById(config.currentStartId);
            const errorBox = form.querySelector(".client-errors");
            const inputs = {
                startLat: form.querySelector("[name='start_latitude']"),
                startLng: form.querySelector("[name='start_longitude']"),
                endLat: form.querySelector("[name='end_latitude']"),
                endLng: form.querySelector("[name='end_longitude']")
            };
            const map = L.map(config.mapId).setView([9.7786, 118.7353], 15);
            let selectedPinMode = "start";
            let startMarker = null;
            let endMarker = null;
            let routeLine = null;

            addBaseLayers(map);

            function setMode(mode) {
                selectedPinMode = mode;
                startButton.classList.toggle("btn-safewalk", mode === "start");
                startButton.classList.toggle("btn-outline-primary", mode !== "start");
                startButton.classList.toggle("active", mode === "start");
                endButton.classList.toggle("btn-safewalk", mode === "end");
                endButton.classList.toggle("btn-outline-primary", mode !== "end");
                endButton.classList.toggle("active", mode === "end");
            }

            function pointValues() {
                return {
                    start: inputs.startLat.value && inputs.startLng.value ? [parseFloat(inputs.startLat.value), parseFloat(inputs.startLng.value)] : null,
                    end: inputs.endLat.value && inputs.endLng.value ? [parseFloat(inputs.endLat.value), parseFloat(inputs.endLng.value)] : null
                };
            }

            function updateLine() {
                const points = pointValues();
                if (routeLine) {
                    map.removeLayer(routeLine);
                    routeLine = null;
                }
                if (points.start && points.end) {
                    routeLine = L.polyline([points.start, points.end], { color: "#0f766e", weight: 4 }).addTo(map);
                    map.fitBounds(routeLine.getBounds(), { padding: [35, 35], maxZoom: 17 });
                    status.textContent = "Route pinned successfully.";
                    status.classList.add("pinned");
                }
            }

            function setPoint(mode, lat, lng, zoom) {
                if (mode === "start") {
                    inputs.startLat.value = lat.toFixed(6);
                    inputs.startLng.value = lng.toFixed(6);
                    if (startMarker) {
                        startMarker.setLatLng([lat, lng]);
                    } else {
                        startMarker = L.marker([lat, lng], { icon: markerIcon("low") }).addTo(map).bindPopup("Start point");
                    }
                    status.textContent = "Start point pinned.";
                    reverseGeocodeAndFill(
                        inputs.startLat.value,
                        inputs.startLng.value,
                        "id_start_location",
                        config.statusId,
                        {
                            loadingText: "Getting start location name...",
                            successText: "Start point pinned.",
                            failureText: "Location name unavailable. You can type the landmark manually.",
                            errorText: "Location name unavailable. You can type the landmark manually."
                        }
                    ).finally(updateLine);
                } else {
                    inputs.endLat.value = lat.toFixed(6);
                    inputs.endLng.value = lng.toFixed(6);
                    if (endMarker) {
                        endMarker.setLatLng([lat, lng]);
                    } else {
                        endMarker = L.marker([lat, lng], { icon: markerIcon("critical") }).addTo(map).bindPopup("End point");
                    }
                    status.textContent = "End point pinned.";
                    reverseGeocodeAndFill(
                        inputs.endLat.value,
                        inputs.endLng.value,
                        "id_end_location",
                        config.statusId,
                        {
                            loadingText: "Getting end location name...",
                            successText: "End point pinned.",
                            failureText: "Location name unavailable. You can type the landmark manually.",
                            errorText: "Location name unavailable. You can type the landmark manually."
                        }
                    ).finally(updateLine);
                }
                status.classList.add("pinned");
                map.setView([lat, lng], zoom || map.getZoom());
            }

            function loadInitialPoints() {
                const points = pointValues();
                if (points.start) {
                    startMarker = L.marker(points.start, { icon: markerIcon("low") }).addTo(map).bindPopup("Start point");
                    map.setView(points.start, 17);
                    status.textContent = "Start point pinned.";
                    status.classList.add("pinned");
                }
                if (points.end) {
                    endMarker = L.marker(points.end, { icon: markerIcon("critical") }).addTo(map).bindPopup("End point");
                    map.setView(points.end, 17);
                    status.textContent = "End point pinned.";
                    status.classList.add("pinned");
                }
                updateLine();
            }

            startButton.addEventListener("click", function () { setMode("start"); });
            endButton.addEventListener("click", function () { setMode("end"); });
            map.on("click", function (event) {
                setPoint(selectedPinMode, event.latlng.lat, event.latlng.lng);
            });
            currentStartButton.addEventListener("click", function () {
                if (!navigator.geolocation) {
                    status.textContent = "Your browser does not support current location.";
                    return;
                }
                status.textContent = "Finding your current location...";
                navigator.geolocation.getCurrentPosition(
                    function (position) {
                        setMode("start");
                        setPoint("start", position.coords.latitude, position.coords.longitude, 17);
                    },
                    function () {
                        status.textContent = "Could not get your current location. You can still click the map.";
                    },
                    { enableHighAccuracy: true, timeout: 10000 }
                );
            });
            form.addEventListener("submit", function (event) {
                const points = pointValues();
                let message = "";
                if (!points.start && !points.end) message = "Please pin your start and end points on the map.";
                else if (!points.start) message = "Please pin your start point.";
                else if (!points.end) message = "Please pin your end point.";
                if (message) {
                    event.preventDefault();
                    status.textContent = message;
                    status.classList.remove("pinned");
                    if (errorBox) {
                        errorBox.classList.remove("d-none");
                        errorBox.innerHTML = escapeHtml(message);
                    }
                }
            });

            setMode("start");
            loadInitialPoints();
            setTimeout(function () { map.invalidateSize(); }, 150);
        }
    };

    function setupReportValidation() {
        document.querySelectorAll(".safewalk-report-form").forEach(function (form) {
            form.addEventListener("submit", function (event) {
                const errors = [];
                const title = form.querySelector("[name='title']");
                const description = form.querySelector("[name='description']");
                const location = form.querySelector("[name='location_name']");
                const latitude = form.querySelector("[name='latitude']");
                const longitude = form.querySelector("[name='longitude']");

                if (!title.value.trim() || title.value.trim().length < 6) {
                    errors.push("Title is required and must be at least 6 characters.");
                }
                if (title.value.length > 120) {
                    errors.push("Title must be 120 characters or fewer.");
                }
                if (!description.value.trim() || description.value.trim().length < 20) {
                    errors.push("Description is required and must be at least 20 characters.");
                }
                if (description.value.length > 2000) {
                    errors.push("Description must be 2,000 characters or fewer.");
                }
                if (!location.value.trim() || location.value.trim().length < 3) {
                    errors.push("Location details / landmark is required and must be at least 3 characters.");
                }

                const lat = parseFloat(latitude.value);
                const lng = parseFloat(longitude.value);
                if (Number.isNaN(lat) || lat < -90 || lat > 90 || Number.isNaN(lng) || lng < -180 || lng > 180) {
                    errors.push("Please pin the unsafe location on the map before submitting.");
                }

                const errorBox = form.querySelector(".client-errors");
                if (errors.length) {
                    event.preventDefault();
                    errorBox.classList.remove("d-none");
                    errorBox.innerHTML = `<strong>Please fix these issues:</strong><ul class="mb-0">${errors.map(function (error) {
                        return `<li>${escapeHtml(error)}</li>`;
                    }).join("")}</ul>`;
                } else if (errorBox) {
                    errorBox.classList.add("d-none");
                    errorBox.innerHTML = "";
                }
            });
        });
    }

    function setupAdminStatusUpdates() {
        document.querySelectorAll(".admin-status-select").forEach(function (select) {
            select.addEventListener("change", function () {
                const reportId = select.dataset.reportId;
                const message = document.querySelector(`[data-status-message="${reportId}"]`);
                const scoreCell = document.querySelector(`[data-score-cell="${reportId}"]`);
                const credibilityCell = document.querySelector(`[data-credibility-cell="${reportId}"]`);
                select.disabled = true;
                if (message) message.textContent = "Saving...";

                fetch(`/api/admin/reports/${reportId}/status/`, {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken()
                    },
                    body: JSON.stringify({ status: select.value, admin_note: "Inline dashboard status update." })
                })
                    .then(function (response) {
                        if (!response.ok) throw new Error("Status update failed.");
                        return response.json();
                    })
                    .then(function (data) {
                        if (scoreCell) scoreCell.textContent = data.safety_score;
                        if (credibilityCell) credibilityCell.textContent = data.credibility_label;
                        if (message) message.textContent = `Saved as ${data.status_display}`;
                    })
                    .catch(function () {
                        if (message) message.textContent = "Could not save. Refresh and try again.";
                    })
                    .finally(function () {
                        select.disabled = false;
                    });
            });
        });
    }

    function weatherCodeInfo(code) {
        const weatherCode = Number(code);
        const conditions = {
            0: ["Clear sky", "bi-brightness-high"],
            1: ["Mainly clear", "bi-brightness-high"],
            2: ["Partly cloudy", "bi-cloud-sun"],
            3: ["Overcast", "bi-cloud"],
            45: ["Fog", "bi-cloud-fog"],
            48: ["Fog", "bi-cloud-fog"],
            51: ["Light drizzle", "bi-cloud-drizzle"],
            53: ["Drizzle", "bi-cloud-drizzle"],
            55: ["Heavy drizzle", "bi-cloud-drizzle"],
            56: ["Freezing drizzle", "bi-cloud-sleet"],
            57: ["Freezing drizzle", "bi-cloud-sleet"],
            61: ["Light rain", "bi-cloud-rain"],
            63: ["Rain", "bi-cloud-rain"],
            65: ["Heavy rain", "bi-cloud-rain-heavy"],
            66: ["Freezing rain", "bi-cloud-sleet"],
            67: ["Freezing rain", "bi-cloud-sleet"],
            71: ["Light snow", "bi-cloud-snow"],
            73: ["Snow", "bi-cloud-snow"],
            75: ["Heavy snow", "bi-cloud-snow"],
            77: ["Snow grains", "bi-cloud-snow"],
            80: ["Rain showers", "bi-cloud-rain"],
            81: ["Rain showers", "bi-cloud-rain-heavy"],
            82: ["Heavy showers", "bi-cloud-rain-heavy"],
            85: ["Snow showers", "bi-cloud-snow"],
            86: ["Snow showers", "bi-cloud-snow"],
            95: ["Scattered thunderstorms", "bi-cloud-lightning-rain"],
            96: ["Thunderstorm with hail", "bi-cloud-lightning-rain"],
            99: ["Heavy thunderstorm", "bi-cloud-lightning-rain"]
        };
        const match = conditions[weatherCode] || ["Mixed conditions", "bi-cloud-sun"];
        return {
            condition: match[0],
            icon: match[1],
            isStorm: weatherCode >= 95,
            isRain: (weatherCode >= 51 && weatherCode <= 67) || (weatherCode >= 80 && weatherCode <= 82)
        };
    }

    function calculateWeatherWalkingRisk(weatherData) {
        const current = weatherData.current || weatherData;
        const temp = Number(current.temp || 0);
        const precipitation = Number(current.precipitation || 0);
        const humidity = Number(current.humidity || 0);
        const wind = Number(current.wind || 0);
        const main = current.main || "";
        const code = Number(current.weather_code || 800);
        const isStorm = main === "Thunderstorm" || (code >= 200 && code <= 232);
        const isRain = main === "Rain" || main === "Drizzle" || (code >= 300 && code <= 531);
        const isLowVisibility = ["Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"].includes(main);

        if (temp >= 36 || (isStorm && precipitation >= 80) || wind >= 50) {
            return {
                level: "Critical",
                type: "danger",
                title: "Critical Weather Risk",
                message: "Unsafe walking weather is likely in this area.",
                advice: "Avoid walking if possible. Wait for conditions to improve and use only well-lit, sheltered routes for urgent trips."
            };
        }
        if (isStorm || (temp >= 33 && humidity >= 70)) {
            return {
                level: "High",
                type: "danger",
                title: isStorm ? "Thunderstorm Watch" : "Excessive Heat",
                message: isStorm ? "Thunderstorms can create lightning, flooding, and poor visibility hazards." : "Severe heat is expected in this area.",
                advice: "Avoid long walks during peak heat. Bring water, use shaded routes, and avoid flood-prone shortcuts if rain starts."
            };
        }
        if (temp >= 33 || precipitation >= 70 || isRain || wind >= 30 || isLowVisibility || precipitation >= 45) {
            return {
                level: "Medium",
                type: "caution",
                title: "Weather Caution",
                message: "Weather may make some walking routes less safe.",
                advice: "Bring rain protection or water, choose shaded and well-drained routes, and avoid slippery sidewalks."
            };
        }
        return {
            level: "Low",
            type: "safe",
            title: "Safe Walking Weather",
            message: "Weather is generally safe for walking.",
            advice: "Use your normal route, stay alert at crossings, and check active SafeWalk reports nearby."
        };
    }

    function clampNumber(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function rounded(value, fallback) {
        const number = Number(value);
        return Number.isFinite(number) ? Math.round(number) : fallback;
    }

    function formatWeekday(value, fallback) {
        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) return fallback || "";
        return new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(date);
    }

    function formatFullWeekday(value) {
        const date = value ? new Date(value.includes("T") ? value : `${value}T00:00:00`) : new Date();
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(date);
    }

    function formatHour(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat(undefined, { hour: "numeric" }).format(date).replace(" ", "");
    }

    function formatUpdatedTime(value) {
        const date = value ? new Date(value) : new Date();
        if (Number.isNaN(date.getTime())) return "Updated recently";
        return `Updated ${new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date)}`;
    }

    function metricSettings(metric) {
        return {
            temperature: {
                key: "temperature",
                suffix: "C",
                color: "#fbbc04",
                fill: "#fef3c7",
                label: "Hourly temperature graph"
            },
            precipitation: {
                key: "precipitation",
                suffix: "%",
                color: "#2563eb",
                fill: "#dbeafe",
                label: "Hourly precipitation probability graph"
            },
            wind: {
                key: "wind",
                suffix: " km/h",
                color: "#0f766e",
                fill: "#ccfbf1",
                label: "Hourly wind speed graph"
            }
        }[metric] || {
            key: "temperature",
            suffix: "C",
            color: "#fbbc04",
            fill: "#fef3c7",
            label: "Hourly temperature graph"
        };
    }

    function buildHourlySeries(hourly, metric) {
        const settings = metricSettings(metric);
        return (hourly || []).slice(0, 8).map(function (point) {
            return {
                label: point.label || "",
                value: rounded(point[settings.key], 0)
            };
        });
    }

    function renderHourlyGraph(chart, hourly, metric) {
        if (!chart) return;
        const settings = metricSettings(metric);
        const series = buildHourlySeries(hourly, metric);
        if (series.length < 2) return;

        const width = 760;
        const height = 150;
        const top = 20;
        const bottom = 34;
        const left = 28;
        const right = 28;
        const values = series.map(function (point) { return point.value; });
        let min = Math.min.apply(null, values);
        let max = Math.max.apply(null, values);
        if (min === max) {
            min -= 1;
            max += 1;
        }
        const range = max - min;
        const xStep = (width - left - right) / (series.length - 1);

        function x(index) {
            return left + (index * xStep);
        }

        function y(value) {
            return top + ((max - value) / range) * (height - top - bottom);
        }

        const linePoints = series.map(function (point, index) {
            return `${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`;
        });
        const linePath = `M ${linePoints.join(" L ")}`;
        const areaPath = `${linePath} L ${x(series.length - 1).toFixed(1)} ${height - bottom} L ${left} ${height - bottom} Z`;
        const valueLabels = series.map(function (point, index) {
            return `<text x="${x(index).toFixed(1)}" y="${Math.max(14, y(point.value) - 10).toFixed(1)}" text-anchor="middle" class="weather-chart-value">${point.value}</text>`;
        }).join("");
        const timeLabels = series.map(function (point, index) {
            if (!point.label) return "";
            return `<text x="${x(index).toFixed(1)}" y="140" text-anchor="middle" class="weather-chart-time">${escapeHtml(point.label)}</text>`;
        }).join("");

        chart.innerHTML = `
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(settings.label)}">
                <path d="${areaPath}" fill="${settings.fill}"></path>
                <path d="${linePath}" fill="none" stroke="${settings.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
                ${series.map(function (point, index) {
                    return `<circle cx="${x(index).toFixed(1)}" cy="${y(point.value).toFixed(1)}" r="3" fill="${settings.color}"><title>${point.value}${escapeHtml(settings.suffix)} ${escapeHtml(point.label)}</title></circle>`;
                }).join("")}
                ${valueLabels}
                ${timeLabels}
            </svg>
        `;
    }

    function normalizeOpenMeteoData(data, locationLabel) {
        const current = data.current || {};
        const daily = data.daily || {};
        const hourly = data.hourly || {};
        const condition = weatherCodeInfo(current.weather_code || (daily.weather_code || [])[0]);
        const weatherData = {
            source: "open-meteo",
            location: locationLabel,
            current: {
                temp: rounded(current.temperature_2m, rounded((daily.temperature_2m_max || [])[0], 33)),
                condition: condition.condition,
                main: condition.isStorm ? "Thunderstorm" : condition.isRain ? "Rain" : "Clouds",
                weather_code: current.weather_code || 800,
                precipitation: clampNumber(rounded((daily.precipitation_probability_max || [])[0], 45), 0, 100),
                humidity: clampNumber(rounded(current.relative_humidity_2m, rounded((hourly.relative_humidity_2m || [])[0], 72)), 0, 100),
                wind: rounded(current.wind_speed_10m, rounded((daily.wind_speed_10m_max || [])[0], 8)),
                icon: condition.icon,
                icon_url: "",
                day: formatFullWeekday(current.time || (daily.time || [])[0]),
                updated: "Updated recently"
            },
            hourly: (hourly.time || []).slice(0, 8).map(function (time, index) {
                return {
                    label: formatHour(time),
                    temperature: rounded((hourly.temperature_2m || [])[index], 0),
                    precipitation: rounded((hourly.precipitation_probability || [])[index], 0),
                    wind: rounded((hourly.wind_speed_10m || [])[index], 0),
                    humidity: rounded((hourly.relative_humidity_2m || [])[index], 0)
                };
            }),
            forecast: (daily.time || []).slice(0, 8).map(function (time, index) {
                const dayInfo = weatherCodeInfo((daily.weather_code || [])[index]);
                return {
                    weekday: formatWeekday(time, `Day ${index + 1}`),
                    condition: dayInfo.condition,
                    main: dayInfo.isStorm ? "Thunderstorm" : dayInfo.isRain ? "Rain" : "Clouds",
                    icon: dayInfo.icon,
                    icon_url: "",
                    temp_max: rounded((daily.temperature_2m_max || [])[index], 0),
                    temp_min: rounded((daily.temperature_2m_min || [])[index], 0),
                    precipitation: rounded((daily.precipitation_probability_max || [])[index], 0)
                };
            })
        };
        const risk = calculateWeatherWalkingRisk(weatherData);
        weatherData.alert = {
            title: risk.title,
            type: risk.type,
            location: locationLabel,
            time: "Updated recently",
            message: risk.message
        };
        weatherData.walking_advice = {
            risk_level: risk.level,
            advice: risk.advice
        };
        return weatherData;
    }

    function initLandingWeather() {
        const panel = document.querySelector("[data-weather-panel]");
        if (!panel) return;

        const status = panel.querySelector("[data-weather-status]");
        const forecastList = panel.querySelector("[data-weather-list]");
        const refreshButton = panel.querySelector("[data-weather-refresh]");
        const locationButton = panel.querySelector("[data-weather-location]");
        const chart = panel.querySelector("[data-weather-chart]");
        const tabs = panel.querySelectorAll("[data-weather-tab]");
        const initialDataNode = document.getElementById("weather-dashboard-data");
        const defaultCoords = {
            lat: parseFloat(panel.dataset.weatherLat) || 9.7786,
            lng: parseFloat(panel.dataset.weatherLng) || 118.7353,
            label: panel.dataset.weatherLocation || "Tiniguiban, Puerto Princesa City"
        };
        let activeCoords = defaultCoords;
        let activeMetric = "temperature";
        let latestWeatherData = null;

        function setStatus(message) {
            if (status) status.textContent = message;
        }

        function setText(selector, value) {
            panel.querySelectorAll(selector).forEach(function (element) {
                element.textContent = value;
            });
        }

        function renderWeatherDashboard(data) {
            const current = data.current || {};
            const alertData = data.alert || {};
            const adviceData = data.walking_advice || {};
            const icon = panel.querySelector("[data-weather-primary-icon]");
            const iconImg = panel.querySelector("[data-weather-current-icon-img]");
            if (current.icon_url && iconImg) {
                iconImg.src = current.icon_url;
                iconImg.alt = current.condition || "Current weather";
                iconImg.hidden = false;
                if (icon) icon.hidden = true;
            } else {
                if (iconImg) {
                    iconImg.removeAttribute("src");
                    iconImg.hidden = true;
                }
                if (icon) {
                    icon.className = `bi ${current.icon || "bi-cloud-sun"}`;
                    icon.hidden = false;
                }
            }

            latestWeatherData = data;
            setText("[data-weather-location-name]", data.location || defaultCoords.label);
            setText("[data-weather-current-temp]", rounded(current.temp, 33));
            setText("[data-weather-current-precipitation]", `${rounded(current.precipitation, 45)}%`);
            setText("[data-weather-current-humidity]", `${rounded(current.humidity, 72)}%`);
            setText("[data-weather-current-wind]", `${rounded(current.wind, 8)} km/h`);
            setText("[data-weather-current-day]", current.day || formatFullWeekday(new Date().toISOString()));
            setText("[data-weather-primary-condition]", current.condition || "Scattered thunderstorms");

            if (forecastList) {
                forecastList.innerHTML = (data.forecast || []).slice(0, 8).map(function (day, index) {
                    const iconMarkup = day.icon_url
                        ? `<img class="forecast-weather-img" src="${escapeHtml(day.icon_url)}" alt="${escapeHtml(day.condition || "Forecast weather")}">`
                        : `<i class="bi ${escapeHtml(day.icon)}" aria-hidden="true"></i>`;
                    return `
                        <article class="forecast-day-card${index === 0 ? " active" : ""}">
                            <span>${escapeHtml(day.weekday)}</span>
                            ${iconMarkup}
                            <strong>${rounded(day.temp_max, 0)}&deg;</strong>
                            <small>${rounded(day.temp_min, 0)}&deg;</small>
                        </article>
                    `;
                }).join("");
            }

            const alert = panel.querySelector(".weather-alert");
            const advice = panel.querySelector(".walking-advice-card");
            const type = alertData.type || adviceData.type || "safe";
            if (alert) alert.className = `weather-alert ${type}`;
            if (advice) advice.className = `walking-advice-card ${type}`;
            const riskPill = panel.querySelector(".weather-risk-pill");
            if (riskPill) riskPill.className = `weather-risk-pill ${type}`;
            setText("[data-weather-alert-title]", alertData.title || "Walking Weather Advisory");
            setText("[data-weather-alert-location]", alertData.location || data.location || defaultCoords.label);
            setText("[data-weather-alert-time]", alertData.time || current.updated || "Updated recently");
            setText("[data-weather-alert-message]", alertData.message || "Check conditions before walking.");
            setText("[data-weather-risk-level]", adviceData.risk_level || "Low");
            setText("[data-weather-advice]", adviceData.advice || "Use normal walking precautions and check nearby SafeWalk reports.");

            renderHourlyGraph(chart, data.hourly || [], activeMetric);
            setStatus(`Showing forecast for ${data.location || defaultCoords.label}.`);
        }

        async function loadOpenMeteoFallback(coords) {
            const params = new URLSearchParams({
                latitude: coords.lat,
                longitude: coords.lng,
                current: "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                hourly: "temperature_2m,precipitation_probability,wind_speed_10m,relative_humidity_2m",
                daily: "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
                timezone: "auto",
                forecast_days: "7"
            });

            const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params.toString()}`);
            if (!response.ok) throw new Error("Weather fallback request failed.");
            return normalizeOpenMeteoData(await response.json(), coords.label || defaultCoords.label);
        }

        async function loadForecast(coords) {
            const params = new URLSearchParams({
                lat: coords.lat,
                lon: coords.lng
            });
            if (coords.label && coords.label !== "Current location") params.set("location", coords.label);

            setStatus(`Loading forecast for ${coords.label || defaultCoords.label}...`);
            try {
                const response = await fetch(`/api/weather/?${params.toString()}`);
                if (!response.ok) throw new Error("Weather API request failed.");
                return response.json();
            } catch (error) {
                return loadOpenMeteoFallback(coords);
            }
        }

        function refreshForecast() {
            if (refreshButton) refreshButton.disabled = true;
            loadForecast(activeCoords)
                .then(renderWeatherDashboard)
                .catch(function () {
                    setStatus("Live forecast is unavailable. Showing saved sample forecast.");
                })
                .finally(function () {
                    if (refreshButton) refreshButton.disabled = false;
                });
        }

        tabs.forEach(function (tab) {
            tab.addEventListener("click", function () {
                activeMetric = tab.dataset.weatherTab || "temperature";
                tabs.forEach(function (item) {
                    const selected = item === tab;
                    item.classList.toggle("active", selected);
                    item.setAttribute("aria-selected", selected ? "true" : "false");
                });
                renderHourlyGraph(chart, latestWeatherData ? latestWeatherData.hourly : [], activeMetric);
            });
        });

        if (refreshButton) {
            refreshButton.addEventListener("click", refreshForecast);
        }

        if (locationButton) {
            locationButton.addEventListener("click", function () {
                if (!navigator.geolocation) {
                    setStatus("Current location is unavailable in this browser.");
                    return;
                }

                locationButton.disabled = true;
                setStatus("Finding your current location...");
                navigator.geolocation.getCurrentPosition(
                    function (position) {
                        activeCoords = {
                            lat: position.coords.latitude,
                            lng: position.coords.longitude,
                            label: "Current location"
                        };
                        refreshForecast();
                        locationButton.disabled = false;
                    },
                    function () {
                        setStatus("Could not access your location. Showing the default forecast.");
                        locationButton.disabled = false;
                    },
                    { enableHighAccuracy: false, timeout: 10000 }
                );
            });
        }

        if (initialDataNode) {
            try {
                renderWeatherDashboard(JSON.parse(initialDataNode.textContent || "{}"));
            } catch (error) {
                refreshForecast();
            }
        } else {
            refreshForecast();
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupReportValidation();
        setupAdminStatusUpdates();
        initLandingWeather();
    });
})();
