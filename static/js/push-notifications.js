(function () {
    "use strict";

    const statusNodes = document.querySelectorAll("[data-push-status]");
    const enableButtons = document.querySelectorAll("[data-push-enable]");
    const publicKey = document.querySelector('meta[name="vapid-public-key"]')?.content || "";

    function setStatus(message, type) {
        statusNodes.forEach(function (node) {
            node.textContent = message;
            node.classList.remove("alert-success", "alert-warning", "alert-danger", "alert-info");
            node.classList.add(type || "alert-info");
        });
    }

    function csrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || "";
    }

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
    }

    async function registerWorker() {
        if (!("serviceWorker" in navigator)) throw new Error("Service worker is not supported.");
        return navigator.serviceWorker.register("/service-worker.js");
    }

    async function subscribeUser() {
        if (!("Notification" in window) || !("PushManager" in window)) {
            setStatus("Push notifications are not supported in this browser.", "alert-warning");
            return;
        }
        if (!publicKey) {
            setStatus("Push notifications are not configured yet. Add VAPID keys on the server.", "alert-warning");
            return;
        }

        const permission = await Notification.requestPermission();
        if (permission === "denied") {
            setStatus("Notifications are blocked. Please enable them in your browser settings.", "alert-danger");
            return;
        }
        if (permission !== "granted") {
            setStatus("Notification permission was not granted.", "alert-warning");
            return;
        }

        const registration = await registerWorker();
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey)
            });
        }

        const response = await fetch("/api/notifications/subscribe/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken()
            },
            credentials: "same-origin",
            body: JSON.stringify(subscription)
        });
        if (!response.ok) throw new Error("Subscription could not be saved.");
        setStatus("Notifications enabled.", "alert-success");
    }

    async function unsubscribeUser() {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
            await fetch("/api/notifications/unsubscribe/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken()
                },
                credentials: "same-origin",
                body: JSON.stringify({ endpoint: subscription.endpoint })
            });
            await subscription.unsubscribe();
        }
        setStatus("Notifications disabled on this device.", "alert-info");
    }

    enableButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            button.disabled = true;
            subscribeUser().catch(function (error) {
                console.warn("SafeWalk push setup failed:", error);
                setStatus("Notifications could not be enabled on this device.", "alert-danger");
            }).finally(function () {
                button.disabled = false;
            });
        });
    });

    document.querySelectorAll("[data-push-unsubscribe]").forEach(function (button) {
        button.addEventListener("click", function () {
            unsubscribeUser().catch(function () {
                setStatus("Could not unsubscribe this device.", "alert-danger");
            });
        });
    });

    window.SafeWalkPushNotifications = { subscribeUser, unsubscribeUser };
})();
