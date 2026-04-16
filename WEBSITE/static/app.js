document.addEventListener("DOMContentLoaded", () => {
    const loadingOverlay = document.getElementById("loadingOverlay");
    const loadingTitle = document.getElementById("loadingTitle");
    const loadingMessage = document.getElementById("loadingMessage");
    const forms = document.querySelectorAll(".tool-form");

    const resetLoadingState = () => {
        document.body.classList.remove("is-loading");
        document.body.removeAttribute("aria-busy");
        loadingOverlay?.setAttribute("aria-hidden", "true");

        document.querySelectorAll("[data-submit-button]").forEach((button) => {
            button.disabled = false;
            const defaultLabel = button.dataset.defaultLabel;
            if (defaultLabel) {
                button.textContent = defaultLabel;
            }
        });
    };

    window.addEventListener("pageshow", resetLoadingState);

    forms.forEach((form) => {
        form.addEventListener("submit", () => {
            const title = form.dataset.loadingTitle || "Scraping sedang berjalan";
            const message =
                form.dataset.loadingMessage ||
                "Mohon tunggu. Browser dan request TikTok sedang diproses.";

            if (loadingTitle) {
                loadingTitle.textContent = title;
            }

            if (loadingMessage) {
                loadingMessage.textContent = message;
            }

            document.body.classList.add("is-loading");
            document.body.setAttribute("aria-busy", "true");
            loadingOverlay?.setAttribute("aria-hidden", "false");

            const submitButton = form.querySelector("[data-submit-button]");
            if (submitButton) {
                submitButton.disabled = true;
                const loadingLabel = submitButton.dataset.loadingLabel;
                if (loadingLabel) {
                    submitButton.textContent = loadingLabel;
                }
            }
        });
    });
});
