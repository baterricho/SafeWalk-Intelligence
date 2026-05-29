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

    function toLeafletPoint(point) {
        if (Array.isArray(point)) return [parseFloat(point[0]), parseFloat(point[1])];
        return [parseFloat(point.lat), parseFloat(point.lng)];
    }

    function routeDistanceKm(points) {
        let total = 0;
        for (let index = 0; index < points.length - 1; index += 1) {
            const start = points[index];
            const end = points[index + 1];
            const radius = 6371;
            const dLat = (end[0] - start[0]) * Math.PI / 180;
            const dLng = (end[1] - start[1]) * Math.PI / 180;
            const lat1 = start[0] * Math.PI / 180;
            const lat2 = end[0] * Math.PI / 180;
            const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
            total += radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        }
        return total;
    }

    function walkingMinutes(distanceKm, apiDurationSeconds, useApiDuration) {
        if (useApiDuration && apiDurationSeconds) return Math.max(1, Math.ceil(apiDurationSeconds / 60));
        return Math.max(1, Math.ceil((distanceKm / 4.8) * 60));
    }

    async function fetchRouteByProfile(start, end, profile, routeType, label, useApiDuration) {
        const url = `https://router.project-osrm.org/route/v1/${profile}/${start[1]},${start[0]};${end[1]},${end[0]}?overview=full&geometries=geojson`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`${profile} route failed`);
        const data = await response.json();
        const route = data.routes && data.routes[0];
        const coordinates = route && route.geometry && route.geometry.coordinates;
        if (!Array.isArray(coordinates) || coordinates.length < 2) throw new Error(`${profile} route unavailable`);
        const points = coordinates.map(function (coordinate) {
            return [coordinate[1], coordinate[0]];
        });
        const distanceKm = route.distance ? route.distance / 1000 : routeDistanceKm(points);
        return {
            type: routeType,
            label: label,
            points: points,
            geojson: points,
            distanceKm: distanceKm,
            durationMin: walkingMinutes(distanceKm, route.duration, useApiDuration),
            routed: true,
            provider: `osrm-${profile}`
        };
    }

    async function fetchRoadRoute(startLatLng, endLatLng) {
        const start = toLeafletPoint(startLatLng);
        const end = toLeafletPoint(endLatLng);
        try {
            return await fetchRouteByProfile(start, end, "foot", "main_road", "Road-connected route", true);
        } catch (error) {
            try {
                return await fetchRouteByProfile(start, end, "driving", "main_road", "Road-connected route", false);
            } catch (fallbackError) {
                const points = [start, end];
                const distanceKm = routeDistanceKm(points);
                return {
                    points: points,
                    geojson: null,
                    distanceKm: distanceKm,
                    durationMin: walkingMinutes(distanceKm),
                    routed: false,
                    message: "Road route unavailable. Showing direct line temporarily. Try placing the pins closer to a road or walkway."
                };
            }
        }
    }

    async function fetchRouteOptions(startLatLng, endLatLng) {
        const start = toLeafletPoint(startLatLng);
        const end = toLeafletPoint(endLatLng);
        const results = await Promise.allSettled([
            fetchRouteByProfile(start, end, "foot", "shortcut_lane", "Shortcut Lane", true),
            fetchRouteByProfile(start, end, "driving", "main_road", "Main Road", false)
        ]);
        const shortcut = results[0].status === "fulfilled" ? results[0].value : null;
        const mainRoad = results[1].status === "fulfilled" ? results[1].value : null;
        if (shortcut || mainRoad) {
            return { shortcut: shortcut, mainRoad: mainRoad, routed: true };
        }
        const points = [start, end];
        const distanceKm = routeDistanceKm(points);
        const fallback = {
            type: "main_road",
            label: "Direct fallback",
            points: [start, end],
            geojson: null,
            distanceKm: distanceKm,
            durationMin: walkingMinutes(distanceKm),
            routed: false,
            provider: "direct"
        };
        return { shortcut: null, mainRoad: fallback, routed: false };
    }

    function formatRouteMeta(route) {
        if (!route) return "Not available for these points.";
        return `${route.distanceKm.toFixed(1)} km · ${Math.round(route.durationMin)} min walk`;
    }

    function routeLineStyle(type, selected) {
        if (type === "shortcut_lane") {
            return {
                color: "#2563eb",
                weight: selected ? 6 : 5,
                opacity: selected ? 0.95 : 0.85,
                dashArray: "8, 8",
                lineJoin: "round"
            };
        }
        return {
            color: "#0f766e",
            weight: selected ? 7 : 6,
            opacity: selected ? 0.98 : 0.9,
            lineJoin: "round"
        };
    }

    window.SafeWalkRouting = {
        fetchRoadRoute: fetchRoadRoute,
        fetchRouteOptions: fetchRouteOptions
    };

    window.SafeWalkDashboard = {
        init: function (config) {
            const dataNode = document.getElementById(config.dataElement);
            if (!dataNode || !window.L) return;
            let reports = JSON.parse(dataNode.textContent || "[]");
            let reportsSignature = reportSignature(reports);
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
            const status = config.statusId ? document.getElementById(config.statusId) : null;
            const clear = document.getElementById(config.clearId);

            function normalizeReport(report) {
                return Object.assign({}, report, {
                    latitude: Number(report.latitude),
                    longitude: Number(report.longitude)
                });
            }

            function reportSignature(items) {
                return (items || []).map(function (report) {
                    return [
                        report.id,
                        report.status,
                        report.safety_score,
                        report.credibility_label,
                        report.updated_at || ""
                    ].join(":");
                }).join("|");
            }

            function filteredReports() {
                const q = (search.value || "").toLowerCase().trim();
                return reports.filter(function (report) {
                    const haystack = `${report.title} ${report.description} ${report.location_name}`.toLowerCase();
                    return (!q || haystack.includes(q))
                        && (!category.value || report.category === category.value)
                        && (!risk.value || report.risk_level === risk.value)
                        && (!status || !status.value || report.status === status.value);
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
                            </div>
                            <a class="btn btn-sm btn-outline-teal" href="${report.detail_url}">View Details</a>
                        </div>
                        <div class="community-line small mt-3">
                            ${report.confirmation_count || 0} community signals - ${report.comment_count || 0} comments
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

            [search, category, risk, status].filter(Boolean).forEach(function (input) {
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
                    if (status) status.value = "";

                    if (filter === "critical") risk.value = "critical";
                    else if (filter === "high") risk.value = "high";
                    // Note: "nearby" would require geo logic, for now we just show all or leave as is

                    render();
                });
            });

            clear.addEventListener("click", function () {
                search.value = "";
                category.value = "";
                risk.value = "";
                if (status) status.value = "";
                chips.forEach(c => c.classList.remove("active"));
                const allChip = document.querySelector('[data-filter="all"]');
                if (allChip) allChip.classList.add("active");
                render();
            });

            setTimeout(function () {
                map.invalidateSize();
                render();
            }, 100);

            if (config.liveUrl) {
                setInterval(function () {
                    fetch(config.liveUrl, {
                        credentials: "same-origin",
                        cache: "no-store",
                        headers: { "Accept": "application/json" }
                    })
                        .then(function (response) {
                            if (!response.ok) throw new Error("Dashboard refresh failed.");
                            return response.json();
                        })
                        .then(function (data) {
                            const nextReports = (data.reports || []).map(normalizeReport);
                            const nextSignature = reportSignature(nextReports);
                            if (nextSignature !== reportsSignature) {
                                reports = nextReports;
                                reportsSignature = nextSignature;
                                render();
                            }
                        })
                        .catch(function () {
                            // Keep the current dashboard visible if a refresh request fails.
                        });
                }, config.pollInterval || 15000);
            }
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
            const map = L.map(elementId).setView([lat, lng], 17);
            addBaseLayers(map);
            L.marker([lat, lng], { icon: markerIcon(riskKey) })
                .addTo(map)
                .bindPopup(`<strong>${escapeHtml(title)}</strong><br>Risk: ${escapeHtml(risk)}`)
                .openPopup();
            setTimeout(function () { map.invalidateSize(); }, 100);
        }
    };

    window.SafeWalkRouteMap = {
        init: function (elementId, options) {
            const node = document.getElementById(elementId);
            if (!node || !window.L) return;
            const settings = options || {};
            const start = [parseFloat(node.dataset.startLat), parseFloat(node.dataset.startLng)];
            const end = [parseFloat(node.dataset.endLat), parseFloat(node.dataset.endLng)];
            if (start.some(Number.isNaN) || end.some(Number.isNaN)) return;

            const map = L.map(elementId).setView(start, 15);
            addBaseLayers(map);
            const startLabel = node.dataset.startLabel || "Start point";
            const endLabel = node.dataset.endLabel || "End point";
            const startMarker = L.marker(start, { icon: markerIcon("low") })
                .addTo(map)
                .bindPopup(`<strong>Start</strong><br>${escapeHtml(startLabel)}`);
            const endMarker = L.marker(end, { icon: markerIcon("critical") })
                .addTo(map)
                .bindPopup(`<strong>End</strong><br>${escapeHtml(endLabel)}`);

            const status = document.getElementById(node.dataset.statusId || settings.statusId);

            function statusText(message, pinned) {
                if (!status) return;
                status.textContent = message;
                status.classList.toggle("pinned", Boolean(pinned));
            }

            function savedGeometry() {
                const geometryNode = settings.geometryElementId ? document.getElementById(settings.geometryElementId) : null;
                if (!geometryNode) return null;
                try {
                    const geometry = JSON.parse(geometryNode.textContent || "null");
                    return Array.isArray(geometry) && geometry.length > 1 ? geometry : null;
                } catch (error) {
                    return null;
                }
            }

            function savedOptionGeometry(elementId) {
                const geometryNode = elementId ? document.getElementById(elementId) : null;
                if (!geometryNode) return null;
                try {
                    const geometry = JSON.parse(geometryNode.textContent || "null");
                    return Array.isArray(geometry) && geometry.length > 1 ? geometry : null;
                } catch (error) {
                    return null;
                }
            }

            async function drawRoute() {
                const selectedType = settings.selectedRouteType || "main_road";
                const selectedGeometry = savedGeometry();
                const shortcutGeometry = savedOptionGeometry(settings.shortcutGeometryElementId);
                const mainRoadGeometry = savedOptionGeometry(settings.mainRoadGeometryElementId);
                const lines = [];

                if (shortcutGeometry) {
                    lines.push({
                        type: "shortcut_lane",
                        points: shortcutGeometry,
                        selected: selectedType === "shortcut_lane"
                    });
                }
                if (mainRoadGeometry) {
                    lines.push({
                        type: "main_road",
                        points: mainRoadGeometry,
                        selected: selectedType === "main_road"
                    });
                }
                if (!lines.length && selectedGeometry) {
                    lines.push({
                        type: selectedType,
                        points: selectedGeometry,
                        selected: true
                    });
                }

                if (lines.length) {
                    let selectedLine = null;
                    const bounds = [];
                    lines.forEach(function (line) {
                        const polyline = L.polyline(line.points, routeLineStyle(line.type, line.selected)).addTo(map);
                        if (line.selected) selectedLine = polyline;
                        bounds.push(polyline.getBounds());
                    });
                    const fitTarget = selectedLine ? selectedLine.getBounds() : bounds[0];
                    map.fitBounds(fitTarget, { padding: [35, 35], maxZoom: 17 });
                    statusText("Saved route loaded.", true);
                } else {
                    statusText("Finding road-connected route...", false);
                    const routeResult = await fetchRoadRoute(start, end);
                    const routeLine = L.polyline(routeResult.points, routeLineStyle("main_road", true)).addTo(map);
                    map.fitBounds(routeLine.getBounds(), { padding: [35, 35], maxZoom: 17 });
                    if (routeResult.routed) {
                        statusText(`Estimated route: ${routeResult.distanceKm.toFixed(1)} km · ${Math.round(routeResult.durationMin)} min walk`, true);
                    } else {
                        statusText(routeResult.message || "Road route unavailable. Showing direct line temporarily.", false);
                    }
                }
            }

            drawRoute();
            startMarker.openPopup();
            setTimeout(function () { map.invalidateSize(); }, 150);
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
                endLng: form.querySelector("[name='end_longitude']"),
                selectedRouteType: form.querySelector("[name='selected_route_type']"),
                routeGeometry: form.querySelector("[name='route_geometry']"),
                routeDistanceKm: form.querySelector("[name='route_distance_km']"),
                routeDurationMin: form.querySelector("[name='route_duration_min']"),
                shortcutGeometry: form.querySelector("[name='shortcut_geometry']"),
                shortcutDistanceKm: form.querySelector("[name='shortcut_distance_km']"),
                shortcutDurationMin: form.querySelector("[name='shortcut_duration_min']"),
                mainRoadGeometry: form.querySelector("[name='main_road_geometry']"),
                mainRoadDistanceKm: form.querySelector("[name='main_road_distance_km']"),
                mainRoadDurationMin: form.querySelector("[name='main_road_duration_min']")
            };
            const optionsPanel = document.getElementById(config.optionsPanelId || "routeOptionsPanel");
            const optionButtons = optionsPanel ? Array.from(optionsPanel.querySelectorAll("[data-route-option]")) : [];
            const optionMeta = optionsPanel ? {
                shortcut_lane: optionsPanel.querySelector("[data-route-option-meta='shortcut_lane']"),
                main_road: optionsPanel.querySelector("[data-route-option-meta='main_road']")
            } : {};
            const map = L.map(config.mapId).setView([9.7786, 118.7353], 15);
            let selectedPinMode = "start";
            let startMarker = null;
            let endMarker = null;
            let routeLines = {};
            let routeRequestId = 0;
            let currentRouteOptions = {};

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

            function clearRouteMetadata() {
                currentRouteOptions = {};
                if (inputs.selectedRouteType) inputs.selectedRouteType.value = "";
                if (inputs.routeGeometry) inputs.routeGeometry.value = "";
                if (inputs.routeDistanceKm) inputs.routeDistanceKm.value = "";
                if (inputs.routeDurationMin) inputs.routeDurationMin.value = "";
                if (inputs.shortcutGeometry) inputs.shortcutGeometry.value = "";
                if (inputs.shortcutDistanceKm) inputs.shortcutDistanceKm.value = "";
                if (inputs.shortcutDurationMin) inputs.shortcutDurationMin.value = "";
                if (inputs.mainRoadGeometry) inputs.mainRoadGeometry.value = "";
                if (inputs.mainRoadDistanceKm) inputs.mainRoadDistanceKm.value = "";
                if (inputs.mainRoadDurationMin) inputs.mainRoadDurationMin.value = "";
                if (optionsPanel) optionsPanel.classList.add("d-none");
            }

            function setOptionFields(prefix, option) {
                const geometryInput = inputs[`${prefix}Geometry`];
                const distanceInput = inputs[`${prefix}DistanceKm`];
                const durationInput = inputs[`${prefix}DurationMin`];
                if (geometryInput) geometryInput.value = option && option.geojson ? JSON.stringify(option.geojson) : "";
                if (distanceInput) distanceInput.value = option && option.distanceKm ? option.distanceKm.toFixed(2) : "";
                if (durationInput) durationInput.value = option && option.durationMin ? String(Math.round(option.durationMin)) : "";
            }

            function chooseRoute(type) {
                const option = currentRouteOptions[type];
                if (!option) return;
                if (inputs.selectedRouteType) inputs.selectedRouteType.value = type;
                if (inputs.routeGeometry) inputs.routeGeometry.value = option.geojson ? JSON.stringify(option.geojson) : "";
                if (inputs.routeDistanceKm) inputs.routeDistanceKm.value = option.distanceKm ? option.distanceKm.toFixed(2) : "";
                if (inputs.routeDurationMin) inputs.routeDurationMin.value = option.durationMin ? String(Math.round(option.durationMin)) : "";
                Object.keys(routeLines).forEach(function (lineType) {
                    routeLines[lineType].setStyle(routeLineStyle(lineType, lineType === type));
                    if (lineType === type) routeLines[lineType].bringToFront();
                });
                optionButtons.forEach(function (button) {
                    button.classList.toggle("selected", button.dataset.routeOption === type);
                    button.disabled = !currentRouteOptions[button.dataset.routeOption];
                });
            }

            function renderRouteOptions(routeOptions) {
                currentRouteOptions = {
                    shortcut_lane: routeOptions.shortcut,
                    main_road: routeOptions.mainRoad
                };
                setOptionFields("shortcut", routeOptions.shortcut);
                setOptionFields("mainRoad", routeOptions.mainRoad);
                if (optionMeta.shortcut_lane) optionMeta.shortcut_lane.textContent = formatRouteMeta(routeOptions.shortcut);
                if (optionMeta.main_road) optionMeta.main_road.textContent = formatRouteMeta(routeOptions.mainRoad);
                if (optionsPanel) optionsPanel.classList.remove("d-none");
                const defaultType = routeOptions.mainRoad ? "main_road" : "shortcut_lane";
                chooseRoute(defaultType);
                const foundCount = [routeOptions.shortcut, routeOptions.mainRoad].filter(function (option) {
                    return option && option.routed;
                }).length;
                if (!routeOptions.routed) {
                    status.textContent = "Could not find a road-connected route. Try placing pins closer to a road.";
                    status.classList.remove("pinned");
                } else if (foundCount === 2) {
                    status.textContent = "Route options found. Choose which route you want to save.";
                    status.classList.add("pinned");
                } else if (foundCount === 1) {
                    status.textContent = "Only one route option is available for these points.";
                    status.classList.add("pinned");
                } else {
                    status.textContent = "Could not find a road-connected route. Try placing pins closer to a road.";
                    status.classList.remove("pinned");
                }
            }

            function setPartialStatus(points) {
                if (points.start && !points.end) {
                    status.textContent = "Start point pinned. Now pin your destination.";
                    status.classList.add("pinned");
                } else if (!points.start && points.end) {
                    status.textContent = "End point pinned. Now pin your starting point.";
                    status.classList.add("pinned");
                } else if (!points.start && !points.end) {
                    status.textContent = "No route pinned yet.";
                    status.classList.remove("pinned");
                }
            }

            async function updateLine() {
                const points = pointValues();
                const currentRequestId = ++routeRequestId;
                Object.values(routeLines).forEach(function (line) { map.removeLayer(line); });
                routeLines = {};
                clearRouteMetadata();
                if (points.start && points.end) {
                    status.textContent = "Finding shortcut lane and main road route...";
                    status.classList.remove("pinned");
                    const routeOptions = await fetchRouteOptions(points.start, points.end);
                    if (currentRequestId !== routeRequestId) return;

                    if (routeOptions.shortcut) {
                        routeLines.shortcut_lane = L.polyline(routeOptions.shortcut.points, routeLineStyle("shortcut_lane", false)).addTo(map);
                    }
                    if (routeOptions.mainRoad) {
                        routeLines.main_road = L.polyline(routeOptions.mainRoad.points, routeLineStyle("main_road", true)).addTo(map);
                    }
                    const lines = Object.values(routeLines);
                    if (lines.length) map.fitBounds(L.featureGroup(lines).getBounds(), { padding: [35, 35], maxZoom: 17 });
                    renderRouteOptions(routeOptions);
                } else {
                    setPartialStatus(points);
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
                    status.textContent = "Start point pinned. Now pin your destination.";
                    reverseGeocodeAndFill(
                        inputs.startLat.value,
                        inputs.startLng.value,
                        "id_start_location",
                        config.statusId,
                        {
                            loadingText: "Getting start location name...",
                            successText: "Start point pinned. Now pin your destination.",
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
                    status.textContent = "End point pinned. Now pin your starting point.";
                    reverseGeocodeAndFill(
                        inputs.endLat.value,
                        inputs.endLng.value,
                        "id_end_location",
                        config.statusId,
                        {
                            loadingText: "Getting end location name...",
                            successText: "End point pinned. Now pin your starting point.",
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
                    status.textContent = "Start point pinned. Now pin your destination.";
                    status.classList.add("pinned");
                }
                if (points.end) {
                    endMarker = L.marker(points.end, { icon: markerIcon("critical") }).addTo(map).bindPopup("End point");
                    map.setView(points.end, 17);
                    status.textContent = "End point pinned. Now pin your starting point.";
                    status.classList.add("pinned");
                }
                updateLine();
            }

            startButton.addEventListener("click", function () { setMode("start"); });
            endButton.addEventListener("click", function () { setMode("end"); });
            optionButtons.forEach(function (button) {
                button.addEventListener("click", function () {
                    chooseRoute(button.dataset.routeOption);
                });
            });
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
        const index = calculateWeatherSafetyIndex(weatherData.current || weatherData);
        return {
            level: index.index_label,
            type: index.type,
            title: index.index_label === "Safe" ? "Safe Walking Weather" : `${index.index_label} Weather`,
            message: (index.risk_reasons || []).join(", "),
            advice: index.advice
        };
    }

    function calculateWeatherSafetyIndex(weatherData) {
        const current = weatherData.current || weatherData;
        const temp = Number(current.temp || 0);
        const precipitation = Number(current.precipitation || 0);
        const humidity = Number(current.humidity || 0);
        const wind = Number(current.wind || 0);
        const main = current.main || "";
        const code = Number(current.weather_code || 800);
        const isStorm = main === "Thunderstorm" || (code >= 200 && code <= 232);
        const isLowVisibility = ["Mist", "Smoke", "Haze", "Dust", "Fog", "Sand", "Ash"].includes(main);
        let probability = 0;
        const reasons = [];
        if (precipitation > 70) {
            probability += 35;
            reasons.push(`Rain probability ${precipitation}%`);
        } else if (precipitation > 40) {
            probability += 20;
            reasons.push(`Rain probability ${precipitation}%`);
        }
        if (isStorm) {
            probability += 30;
            reasons.push(current.condition || "Thunderstorm condition");
        }
        if (temp >= 36) {
            probability += 35;
            reasons.push(`High temperature ${temp}C`);
        } else if (temp >= 33) {
            probability += 20;
            reasons.push(`High temperature ${temp}C`);
        }
        if (wind > 35) {
            probability += 30;
            reasons.push(`Strong wind ${wind} km/h`);
        } else if (wind > 20) {
            probability += 15;
            reasons.push(`Wind ${wind} km/h`);
        }
        if (humidity > 75) {
            probability += 10;
            reasons.push(`Humidity ${humidity}%`);
        }
        if (isLowVisibility) {
            probability += 20;
            reasons.push("Poor visibility");
        }
        probability = clampNumber(probability, 0, 100);
        let label = "Safe";
        let key = "safe";
        let advice = "Good walking condition. Stay aware of traffic and nearby SafeWalk reports.";
        if (probability > 80) {
            label = "Critical Risk";
            key = "critical";
            advice = "Avoid walking if possible. Wait for conditions to improve.";
        } else if (probability > 60) {
            label = "High Risk";
            key = "high";
            advice = "Walking may be unsafe in exposed or poorly lit areas. Use visible main roads.";
        } else if (probability > 40) {
            label = "Moderate Risk";
            key = "moderate";
            advice = "Use caution while walking. Bring rain protection or water if needed.";
        } else if (probability > 20) {
            label = "Low Risk";
            key = "low";
            advice = "Minor weather concern. Use normal walking precautions.";
        }
        return {
            index_label: label,
            index_probability: probability,
            index_key: key,
            type: key === "critical" || key === "high" ? "danger" : key === "moderate" ? "caution" : "safe",
            advice: advice,
            risk_reasons: reasons.length ? reasons : ["Weather conditions are generally favorable."]
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

    function formatDate(value, short) {
        const date = value ? new Date(value.includes("T") ? value : `${value}T00:00:00`) : new Date();
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat(undefined, short ? { month: "short", day: "numeric" } : { month: "long", day: "numeric", year: "numeric" }).format(date);
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

    function formatSunTime(isoString) {
        if (!isoString) return '';
        var d = new Date(isoString);
        if (isNaN(d.getTime())) return '';
        return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(d);
    }

    function uvLabel(index) {
        var uv = Math.round(Number(index) || 0);
        if (uv <= 2) return 'Low';
        if (uv <= 5) return 'Moderate';
        if (uv <= 7) return 'High';
        if (uv <= 10) return 'Very High';
        return 'Extreme';
    }

    function reverseGeocode(lat, lng) {
        return fetch('https://nominatim.openstreetmap.org/reverse?lat=' + lat + '&lon=' + lng + '&format=json&zoom=14')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (!data || !data.address) return null;
                var addr = data.address;
                var parts = [];
                if (addr.suburb || addr.neighbourhood || addr.village) parts.push(addr.suburb || addr.neighbourhood || addr.village);
                if (addr.city || addr.town || addr.municipality) parts.push(addr.city || addr.town || addr.municipality);
                return parts.join(', ') || data.display_name || null;
            })
            .catch(function() { return null; });
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
                feels_like: rounded(current.apparent_temperature, rounded((daily.apparent_temperature_max || [])[0], 33)),
                uv_index: rounded((hourly.uv_index || [])[0], 0),
                pressure: rounded(current.surface_pressure, 1013),
                visibility: rounded((hourly.visibility || [])[0], 10000) / 1000,
                dew_point: rounded((hourly.dew_point_2m || [])[0], 25),
                sunrise: formatSunTime((daily.sunrise || [])[0]),
                sunset: formatSunTime((daily.sunset || [])[0]),
                icon: condition.icon,
                icon_url: "",
                day: formatFullWeekday(current.time || (daily.time || [])[0]),
                date: formatDate(current.time || (daily.time || [])[0]),
                date_short: formatDate(current.time || (daily.time || [])[0], true),
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
                    day: formatFullWeekday(time),
                    date: formatDate(time),
                    date_short: formatDate(time, true),
                    condition: dayInfo.condition,
                    main: dayInfo.isStorm ? "Thunderstorm" : dayInfo.isRain ? "Rain" : "Clouds",
                    icon: dayInfo.icon,
                    icon_url: "",
                    temp_max: rounded((daily.temperature_2m_max || [])[index], 0),
                    temp_min: rounded((daily.temperature_2m_min || [])[index], 0),
                    high: rounded((daily.temperature_2m_max || [])[index], 0),
                    low: rounded((daily.temperature_2m_min || [])[index], 0),
                    temperature: rounded((daily.temperature_2m_max || [])[index], 0),
                    precipitation: rounded((daily.precipitation_probability_max || [])[index], 0),
                    rain_probability: rounded((daily.precipitation_probability_max || [])[index], 0),
                    humidity: rounded((hourly.relative_humidity_2m || [])[index], 0),
                    wind: rounded((daily.wind_speed_10m_max || [])[index], 0),
                    wind_speed: rounded((daily.wind_speed_10m_max || [])[index], 0)
                };
            })
        };
        weatherData.current = Object.assign(weatherData.current, calculateWeatherSafetyIndex(weatherData.current));
        weatherData.forecast = weatherData.forecast.map(function (day, index) {
            return Object.assign(day, calculateWeatherSafetyIndex(day), { is_today: index === 0 });
        });
        weatherData.weather_today = weatherData.current;
        weatherData.daily_forecast = weatherData.forecast;
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
            const today = data.weather_today || current;
            const todayIndex = today.index_label ? today : Object.assign({}, today, calculateWeatherSafetyIndex(today));
            setText("[data-weather-location-name]", data.location || defaultCoords.label);
            setText("[data-weather-current-temp]", rounded(current.temp, 33));
            setText("[data-weather-current-precipitation]", `${rounded(current.precipitation, 45)}%`);
            setText("[data-weather-current-humidity]", `${rounded(current.humidity, 72)}%`);
            setText("[data-weather-current-wind]", `${rounded(current.wind, 8)} km/h`);
            setText("[data-weather-current-day]", current.day || formatFullWeekday(new Date().toISOString()));
            setText("[data-weather-current-date]", today.date || current.date || formatDate(new Date().toISOString()));
            setText("[data-weather-today-date]", `${today.day || current.day || formatFullWeekday(new Date().toISOString())}, ${today.date || formatDate(new Date().toISOString())}`);
            setText("[data-weather-primary-condition]", current.condition || "Scattered thunderstorms");
            setText("[data-weather-index-probability]", `${rounded(todayIndex.index_probability, 0)}%`);

            if (forecastList) {
                forecastList.innerHTML = (data.daily_forecast || data.forecast || []).slice(0, 8).map(function (day, index) {
                    const dayIndex = day.index_label ? day : Object.assign({}, day, calculateWeatherSafetyIndex(day));
                    const iconMarkup = day.icon_url
                        ? `<img class="forecast-weather-img" src="${escapeHtml(day.icon_url)}" alt="${escapeHtml(day.condition || "Forecast weather")}">`
                        : `<i class="bi ${escapeHtml(day.icon)}" aria-hidden="true"></i>`;
                    return `
                        <article class="forecast-day-card weather-calendar-card${index === 0 ? " active" : ""}">
                            <div class="weather-calendar-date">
                                <span>${escapeHtml(day.weekday || day.day || "")}</span>
                                <strong>${escapeHtml(day.date_short || day.date || "")}</strong>
                            </div>
                            <div class="weather-calendar-icon">${iconMarkup}</div>
                            <p>${escapeHtml(day.condition || "Weather update")}</p>
                            <strong class="weather-calendar-temp">${rounded(day.high || day.temp_max, 0)}&deg; / ${rounded(day.low || day.temp_min, 0)}&deg;</strong>
                            <small class="weather-index-badge weather-index-${escapeHtml(dayIndex.index_key)}">${escapeHtml(dayIndex.index_label)}</small>
                            <small class="weather-calendar-probability">Index Probability: ${rounded(dayIndex.index_probability, 0)}%</small>
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
            if (riskPill) riskPill.className = `weather-risk-pill weather-index-${todayIndex.index_key || "safe"} ${type}`;
            setText("[data-weather-alert-title]", alertData.title || "Today’s Walking Safety Index");
            setText("[data-weather-alert-location]", alertData.location || data.location || defaultCoords.label);
            setText("[data-weather-alert-time]", alertData.time || current.updated || "Updated recently");
            setText("[data-weather-alert-message]", alertData.message || (todayIndex.risk_reasons || []).join(", ") || "Check conditions before walking.");
            setText("[data-weather-risk-level]", todayIndex.index_label || adviceData.risk_level || "Safe");
            setText("[data-weather-advice]", todayIndex.advice || adviceData.advice || "Use normal walking precautions and check nearby SafeWalk reports.");

            setText('[data-weather-current-feels-like]', rounded(current.feels_like, 33) + '°C');
            setText('[data-weather-current-uv-index]', rounded(current.uv_index, 0) + ' (' + uvLabel(current.uv_index) + ')');
            setText('[data-weather-current-pressure]', rounded(current.pressure, 1013) + ' hPa');
            setText('[data-weather-current-visibility]', (Math.round((current.visibility || 10) * 10) / 10) + ' km');
            setText('[data-weather-current-dew-point]', rounded(current.dew_point, 25) + '°C');
            setText('[data-weather-current-sunrise]', current.sunrise || '—');
            setText('[data-weather-current-sunset]', current.sunset || '—');

            var liveBadge = panel.querySelector('[data-weather-live-badge]');
            if (liveBadge) {
                liveBadge.classList.add('active');
            }

            renderHourlyGraph(chart, data.hourly || [], activeMetric);
            setStatus(`Showing forecast for ${data.location || defaultCoords.label}.`);
        }

        async function loadOpenMeteoFallback(coords) {
            const params = new URLSearchParams({
                latitude: coords.lat,
                longitude: coords.lng,
                current: "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,apparent_temperature,surface_pressure",
                hourly: "temperature_2m,precipitation_probability,wind_speed_10m,relative_humidity_2m,uv_index,visibility,dew_point_2m",
                daily: "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,apparent_temperature_max,sunrise,sunset",
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

        // Auto-detect user location on page load
        function autoDetectLocation() {
            if (!navigator.geolocation) {
                // No geolocation support, use server data or default
                if (initialDataNode) {
                    try {
                        renderWeatherDashboard(JSON.parse(initialDataNode.textContent || '{}'));
                    } catch (e) {
                        refreshForecast();
                    }
                } else {
                    refreshForecast();
                }
                return;
            }

            // Render server data first for instant display
            if (initialDataNode) {
                try {
                    renderWeatherDashboard(JSON.parse(initialDataNode.textContent || '{}'));
                } catch (e) { /* ignore */ }
            }

            // Then auto-detect location and refresh with precise coordinates
            navigator.geolocation.getCurrentPosition(
                function (position) {
                    activeCoords = {
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                        label: 'Current location'
                    };
                    // Reverse geocode for location name
                    reverseGeocode(position.coords.latitude, position.coords.longitude).then(function(name) {
                        if (name) activeCoords.label = name;
                        refreshForecast();
                    }).catch(function() {
                        refreshForecast();
                    });
                },
                function () {
                    // Geolocation denied - use default, no error shown
                    if (!initialDataNode) {
                        refreshForecast();
                    }
                },
                { enableHighAccuracy: false, timeout: 8000 }
            );
        }

        autoDetectLocation();

        // Auto-refresh every 10 minutes
        setInterval(refreshForecast, 600000);
    }

    function initCookieNotice() {
        const notice = document.querySelector("[data-cookie-notice]");
        if (!notice || localStorage.getItem("safewalk_cookie_notice") === "accepted") return;
        notice.hidden = false;
        const accept = notice.querySelector("[data-cookie-accept]");
        if (accept) {
            accept.addEventListener("click", function () {
                localStorage.setItem("safewalk_cookie_notice", "accepted");
                notice.hidden = true;
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupReportValidation();
        setupAdminStatusUpdates();
        initLandingWeather();
        initCookieNotice();
    });
})();
