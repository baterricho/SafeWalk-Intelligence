(function () {
    "use strict";

    let deferredInstallPrompt = null;

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", function () {
            navigator.serviceWorker.register("/service-worker.js").catch(function (error) {
                console.warn("SafeWalk service worker registration failed:", error);
            });
        });
    }

    window.addEventListener("beforeinstallprompt", function (event) {
        event.preventDefault();
        deferredInstallPrompt = event;
        document.dispatchEvent(new CustomEvent("safewalk:pwa-install-ready"));
    });

    window.SafeWalkPWA = {
        canInstall: function () {
            return Boolean(deferredInstallPrompt);
        },
        promptInstall: async function () {
            if (!deferredInstallPrompt) return false;
            deferredInstallPrompt.prompt();
            const choice = await deferredInstallPrompt.userChoice;
            deferredInstallPrompt = null;
            return choice.outcome === "accepted";
        }
    };
})();
