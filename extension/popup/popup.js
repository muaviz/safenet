// SafeNet - Modern Popup Controller
document.addEventListener("DOMContentLoaded", async () => {
    const childNameEl = document.getElementById("childName");
    const rulesCountEl = document.getElementById("rulesCount");
    const lastSyncedEl = document.getElementById("lastSynced");
    const tierBadgeEl = document.getElementById("tierBadge");
    const liveBadge = document.getElementById("liveBadge");
    const liveBadgeText = document.getElementById("liveBadgeText");
    const deviceStatusEl = document.getElementById("deviceStatus");
    const profileAvatar = document.getElementById("profileAvatar");

    const pairingSection = document.getElementById("pairingSection");
    const pairCodeInput = document.getElementById("pairCodeInput");
    const pairBtn = document.getElementById("pairBtn");
    const pairFeedback = document.getElementById("pairFeedback");
    const togglePairingBtn = document.getElementById("togglePairingBtn");

    const refreshBtn = document.getElementById("refreshBtn");
    const syncSpinner = document.getElementById("syncSpinner");
    const syncBtnText = document.getElementById("syncBtnText");
    const syncFeedback = document.getElementById("syncFeedback");
    const openDashboardBtn = document.getElementById("openDashboardBtn");

    function formatRelativeTime(isoString) {
        if (!isoString) return "Never";
        try {
            const date = new Date(isoString);
            const diffSeconds = Math.round((Date.now() - date.getTime()) / 1000);
            if (diffSeconds < 60) return "Just now";
            if (diffSeconds < 3600) return `${Math.round(diffSeconds / 60)}m ago`;
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch {
            return "Recently";
        }
    }

    async function loadStatus() {
        chrome.runtime.sendMessage({ action: "getStatus" }, (status) => {
            if (chrome.runtime.lastError || !status) return;

            if (status.paired && status.child) {
                childNameEl.textContent = status.child.name;
                tierBadgeEl.textContent = `${status.child.safety_tier || 'Moderate'} Mode`;
                deviceStatusEl.textContent = "Synced & Active";
                profileAvatar.textContent = "🛡️";

                liveBadge.className = "status-pill status-active";
                liveBadgeText.textContent = "Protected";
                pairingSection.classList.add("hidden");
                togglePairingBtn.textContent = "Re-pair Device";
            } else {
                childNameEl.textContent = "Unpaired Device";
                tierBadgeEl.textContent = "Default Mode";
                deviceStatusEl.textContent = "Not linked";
                profileAvatar.textContent = "⚠️";

                liveBadge.className = "status-pill status-unpaired";
                liveBadgeText.textContent = "Unpaired";
                pairingSection.classList.remove("hidden");
                togglePairingBtn.textContent = "Close Pairing";
            }

            rulesCountEl.textContent = `${status.rulesCount || 0}`;
            lastSyncedEl.textContent = formatRelativeTime(status.lastSynced);
        });
    }

    // Refresh & Sync rules
    refreshBtn.addEventListener("click", () => {
        refreshBtn.disabled = true;
        syncSpinner.classList.add("spin-anim");
        syncBtnText.textContent = "Syncing Policies...";
        syncFeedback.textContent = "";

        chrome.runtime.sendMessage({ action: "refreshRules" }, (res) => {
            refreshBtn.disabled = false;
            syncSpinner.classList.remove("spin-anim");
            syncBtnText.textContent = "Sync Policies Now";

            if (chrome.runtime.lastError || !res || !res.success) {
                syncFeedback.textContent = `❌ Sync failed: ${(res && res.error) || 'Backend offline'}`;
            } else {
                syncFeedback.textContent = `✅ Synced ${res.count} active security rules!`;
                setTimeout(() => { syncFeedback.textContent = ""; }, 3500);
                loadStatus();
            }
        });
    });

    // Pair device with code
    if (pairBtn) {
        pairBtn.addEventListener("click", () => {
            const code = pairCodeInput.value.trim();
            if (!code || code.length !== 6) {
                pairFeedback.className = "feedback-msg error";
                pairFeedback.textContent = "Please enter a valid 6-digit PIN.";
                return;
            }

            pairBtn.disabled = true;
            pairBtn.textContent = "...";
            pairFeedback.className = "feedback-msg";
            pairFeedback.textContent = "Verifying code with server...";

            chrome.runtime.sendMessage({ action: "pairDevice", code }, (res) => {
                pairBtn.disabled = false;
                pairBtn.textContent = "Pair";

                if (!res || !res.success) {
                    pairFeedback.className = "feedback-msg error";
                    pairFeedback.textContent = res ? res.error : "Invalid code or server offline.";
                } else {
                    pairFeedback.className = "feedback-msg success";
                    pairFeedback.textContent = `Paired with ${res.child.name}!`;
                    pairCodeInput.value = "";
                    setTimeout(loadStatus, 1200);
                }
            });
        });
    }

    // Toggle Pairing Drawer
    if (togglePairingBtn) {
        togglePairingBtn.addEventListener("click", () => {
            pairingSection.classList.toggle("hidden");
            if (!pairingSection.classList.contains("hidden")) {
                pairCodeInput.focus();
                togglePairingBtn.textContent = "Hide Pairing";
            } else {
                togglePairingBtn.textContent = "Re-pair Device";
            }
        });
    }

    // Open Parent Dashboard
    if (openDashboardBtn) {
        openDashboardBtn.addEventListener("click", () => {
            chrome.tabs.create({ url: "http://localhost:5000/dashboard" });
        });
    }

    await loadStatus();
});
