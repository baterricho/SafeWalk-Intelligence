const CACHE_NAME = "safewalk-pwa-v1";
const OFFLINE_URL = "/offline/";

const PRECACHE_URLS = [
    "/",
    OFFLINE_URL,
    "/static/manifest.json",
    "/static/css/style.css",
    "/static/js/main.js",
    "/static/js/pwa.js",
    "/static/images/safewalk-logo.png",
    "/static/images/pwa/icon-192.png",
    "/static/images/pwa/icon-512.png"
];

const PRIVATE_PATH_PREFIXES = [
    "/admin/",
    "/api/",
    "/login/",
    "/signup/",
    "/register/",
    "/logout/",
    "/accounts/",
    "/dashboard/",
    "/admin-dashboard/"
];

function isPrivateRequest(url) {
    return PRIVATE_PATH_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);

    if (request.method !== "GET" || url.origin !== self.location.origin || isPrivateRequest(url)) {
        return;
    }

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request)
                .then((response) => response)
                .catch(() => caches.match(OFFLINE_URL))
        );
        return;
    }

    event.respondWith(
        caches.match(request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;

            return fetch(request)
                .then((response) => {
                    const responseClone = response.clone();
                    if (response.ok && (url.pathname.startsWith("/static/") || url.pathname === "/")) {
                        caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
                    }
                    return response;
                })
                .catch(() => caches.match(OFFLINE_URL));
        })
    );
});
