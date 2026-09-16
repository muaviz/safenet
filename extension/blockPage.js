// SafeNet - Block Page Controller
document.addEventListener("DOMContentLoaded", () => {
    const urlParams = new URLSearchParams(window.location.search);
    const blockedUrl = urlParams.get("blocked") || "restricted-website.com";
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
    const requestFeedbackText = document.getElementById("requestFeedbackText");

    const quoteText = document.getElementById("quoteText");
    const quoteAuthor = document.getElementById("quoteAuthor");

    // Dynamic rotating motivational quotes
    const quotes = [
        { text: "Discipline is choosing between what you want now and what you want most.", author: "— Abraham Lincoln" },
        { text: "It's not that I'm so smart, it's just that I stay with problems longer.", author: "— Albert Einstein" },
        { text: "Focus is a muscle. The more you protect it, the stronger it grows.", author: "— James Clear" },
        { text: "Small daily improvements over time lead to stunning results.", author: "— Robin Sharma" }
    ];
    const randomQuote = quotes[Math.floor(Math.random() * quotes.length)];
    if (quoteText && quoteAuthor) {
        quoteText.textContent = `"${randomQuote.text}"`;
        quoteAuthor.textContent = randomQuote.author;
    }

    if (blockedUrlDisplay) {
        blockedUrlDisplay.textContent = blockedUrl;
    }

    if (blockReasonDisplay && blockReason) {
        blockReasonDisplay.textContent = `Policy: ${blockReason}`;
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

    // Quick Reason Chips
    document.querySelectorAll(".chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            if (requestReasonInput) {
                requestReasonInput.value = chip.getAttribute("data-chip");
                requestReasonInput.focus();
            }
        });
    });

    // Toggle Access Request Drawer
    if (requestAccessBtn && requestModal) {
        requestAccessBtn.addEventListener("click", () => {
            requestModal.classList.toggle("hidden");
            if (!requestModal.classList.contains("hidden") && requestReasonInput) {
                requestReasonInput.focus();
                requestModal.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
                reason: reason || "Requested access for school or study."
            }, (response) => {
                submitRequestBtn.disabled = false;
                submitRequestBtn.textContent = "Send to Parent";

                if (requestModal) requestModal.classList.add("hidden");
                if (requestSuccessMsg) {
                    requestSuccessMsg.classList.remove("hidden");
                    if (response && response.message) {
                        requestFeedbackText.textContent = response.message;
                    }
                }
            });
        });
    }
});
