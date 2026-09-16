// SafeNet - Block Page Interactive Controller
document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const blockedUrl = urlParams.get("blocked") || "Restricted Website";
    const blockReason = urlParams.get("reason");

    const blockedUrlDisplay = document.getElementById("blockedUrlDisplay");
    const blockReasonDisplay = document.getElementById("blockReasonDisplay");
    const goBackBtn = document.getElementById("goBackBtn");
    const requestAccessBtn = document.getElementById("requestAccessBtn");
    const requestModal = document.getElementById("requestModal");
    const cancelRequestBtn = document.getElementById("cancelRequestBtn");
    const submitRequestBtn = document.getElementById("submitRequestBtn");
    const requestReasonInput = document.getElementById("requestReasonInput");
    const requestSuccessMsg = document.getElementById("requestSuccessMsg");

    if (blockedUrlDisplay) {
        blockedUrlDisplay.textContent = blockedUrl;
    }

    if (blockReasonDisplay && blockReason) {
        blockReasonDisplay.textContent = `Reason: ${blockReason}`;
    }

    // Go Back
    if (goBackBtn) {
        goBackBtn.addEventListener("click", () => {
            if (window.history.length > 1) {
                window.history.back();
            } else {
                window.location.href = "https://www.google.com";
            }
        });
    }

    // Toggle Access Request Drawer
    if (requestAccessBtn && requestModal) {
        requestAccessBtn.addEventListener("click", () => {
            requestModal.classList.toggle("hidden");
            if (!requestModal.classList.contains("hidden") && requestReasonInput) {
                requestReasonInput.focus();
            }
        });
    }

    if (cancelRequestBtn && requestModal) {
        cancelRequestBtn.addEventListener("click", () => {
            requestModal.classList.add("hidden");
        });
    }

    // Submit Request
    if (submitRequestBtn) {
        submitRequestBtn.addEventListener("click", async () => {
            const reason = requestReasonInput ? requestReasonInput.value.trim() : "";
            submitRequestBtn.disabled = true;
            submitRequestBtn.textContent = "Sending...";

            chrome.runtime.sendMessage({
                action: "requestAccess",
                url: blockedUrl,
                reason: reason || "Requested access for school/study."
            }, (response) => {
                submitRequestBtn.disabled = false;
                submitRequestBtn.textContent = "Send to Parent";

                if (requestModal) requestModal.classList.add("hidden");
                if (requestSuccessMsg) {
                    requestSuccessMsg.classList.remove("hidden");
                    if (response && response.message) {
                        requestSuccessMsg.textContent = `✅ ${response.message}`;
                    }
                }
            });
        });
    }
});
