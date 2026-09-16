// SafeNet - Popup Logic
document.addEventListener("DOMContentLoaded", async () => {
    const childNameEl = document.getElementById("childName");
    const rulesCountEl = document.getElementById("rulesCount");
    const lastSyncedEl = document.getElementById("lastSynced");
    const pairingSection = document.getElementById("pairingSection");
    const pairCodeInput = document.getElementById("pairCodeInput");
    const pairBtn = document.getElementById("pairBtn");
    const pairFeedback = document.getElementById("pairFeedback");
    const refreshBtn = document.getElementById("refreshBtn");
    const syncFeedback = document.getElementById("syncFeedback");

    function formatTime(isoString) {
        if (!isoString) return "Never";
        try {
            const date = new Date(isoString);
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch {
            return "Recently";
        }
    }

    async function loadStatus() {
        chrome.runtime.sendMessage({ action: "getStatus" }, (status) => {
            if (chrome.runtime.lastError || !status) return;

            if (status.paired && status.child) {
                childNameEl.textContent = `${status.child.name} (${status.child.safety_tier || 'Child'})`;
                pairingSection.classList.add("hidden");
            } else {
                childNameEl.textContent = "Unpaired Device";
                pairingSection.classList.remove("hidden");
            }

            rulesCountEl.textContent = `${status.rulesCount || 0} sites`;
            lastSyncedEl.textContent = formatTime(status.lastSynced);
        });
    }

    // Refresh rules
    refreshBtn.addEventListener("click", () => {
        refreshBtn.disabled = true;
        syncFeedback.textContent = "Syncing with SafeNet server...";

        chrome.runtime.sendMessage({ action: "refreshRules" }, (res) => {
            refreshBtn.disabled = false;
            if (chrome.runtime.lastError || !res || !res.success) {
                syncFeedback.textContent = `❌ Sync failed (${(res && res.error) || 'offline'})`;
            } else {
                syncFeedback.textContent = `✅ Synced ${res.count} blocked sites!`;
                setTimeout(() => { syncFeedback.textContent = ""; }, 3000);
                loadStatus();
            }
        });
    });

    // Pair device with code
    if (pairBtn) {
        pairBtn.addEventListener("click", () => {
            const code = pairCodeInput.value.trim();
            if (!code || code.length !== 6) {
                pairFeedback.className = "feedback-text error";
                pairFeedback.textContent = "Please enter a 6-digit code.";
                return;
            }

            pairBtn.disabled = true;
            pairFeedback.className = "feedback-text";
            pairFeedback.textContent = "Connecting...";

            chrome.runtime.sendMessage({ action: "pairDevice", code }, (res) => {
                pairBtn.disabled = false;
                if (!res || !res.success) {
                    pairFeedback.className = "feedback-text error";
                    pairFeedback.textContent = res ? res.error : "Connection failed.";
                } else {
                    pairFeedback.className = "feedback-text success";
                    pairFeedback.textContent = `Connected to ${res.child.name}!`;
                    pairCodeInput.value = "";
                    setTimeout(loadStatus, 1000);
                }
            });
        });
    }

    await loadStatus();
});
