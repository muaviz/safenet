// SafeNet Extension - Background Service Worker (Manifest V3)
const DEFAULT_API_BASE = "http://localhost:5000";
const BLOCK_PAGE_URL = chrome.runtime.getURL("blockPage.html");

// State
let telemetryQueue = [];
let activeSession = {
    tabId: null,
    domain: null,
    startTime: Date.now()
};
let isUserActive = true;

// Helper: Get API base URL
async function getApiBase() {
    const result = await chrome.storage.local.get(["api_base_url"]);
    return result.api_base_url || DEFAULT_API_BASE;
}

// Helper: Get Device Token
async function getDeviceToken() {
    const result = await chrome.storage.local.get(["device_token"]);
    return result.device_token || null;
}

// Helper: Normalize Domain
function extractDomain(url) {
    try {
        if (!url || !url.startsWith("http")) return null;
        const parsed = new URL(url);
        let hostname = parsed.hostname.toLowerCase();
        if (hostname.startsWith("www.")) {
            hostname = hostname.substring(4);
        }
        return hostname;
    } catch {
        return null;
    }
}

// 1. Sync Rules & Policy
async function syncPolicy() {
    try {
        const apiBase = await getApiBase();
        const deviceToken = await getDeviceToken();

        let blockedSites = [];
        let childInfo = null;

        if (deviceToken) {
            // Paired Mode: Fetch personalized child policy
            const resp = await fetch(`${apiBase}/api/v1/policy`, {
                headers: { "Authorization": `Bearer ${deviceToken}` }
            });
            if (resp.ok) {
                const data = await resp.json();
                blockedSites = data.blocked_sites || [];
                childInfo = data.child || null;
                if (childInfo) {
                    await chrome.storage.local.set({ child_info: childInfo });
                }
            } else if (resp.status === 401) {
                console.warn("[SafeNet] Device token invalid or revoked.");
                await chrome.storage.local.remove(["device_token", "child_info"]);
            }
        }

        // Fallback or Standalone Mode
        if (blockedSites.length === 0) {
            try {
                const fallbackResp = await fetch(`${apiBase}/blocklist`);
                if (fallbackResp.ok) {
                    const fallbackData = await fallbackResp.json();
                    blockedSites = fallbackData.blocked_sites || [];
                }
            } catch (err) {
                console.warn("[SafeNet] Fallback blocklist unreachable:", err.message);
            }
        }

        // Compile DeclarativeNetRequest Dynamic Rules
        const existingRules = await chrome.declarativeNetRequest.getDynamicRules();
        const removeRuleIds = existingRules.map(r => r.id);

        const addRules = blockedSites.map((site, index) => {
            const cleanSite = site.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
            return {
                id: index + 1,
                priority: 1,
                action: {
                    type: "redirect",
                    redirect: { url: `${BLOCK_PAGE_URL}?blocked=${encodeURIComponent(cleanSite)}` }
                },
                condition: {
                    urlFilter: `||${cleanSite}^`,
                    resourceTypes: ["main_frame"]
                }
            };
        });

        // Atomic update of dynamic rules
        await chrome.declarativeNetRequest.updateDynamicRules({
            removeRuleIds,
            addRules
        });

        await chrome.storage.local.set({
            blocked_sites: blockedSites,
            last_synced: new Date().toISOString()
        });

        console.log(`[SafeNet] Policy synced: ${addRules.length} rules active.`);
        return { success: true, count: addRules.length, child: childInfo };
    } catch (error) {
        console.error("[SafeNet] Error syncing policy:", error);
        return { success: false, error: error.message };
    }
}

// 2. Active Screen Time Tracker
function flushCurrentSession() {
    if (!activeSession.domain || !isUserActive) return;

    const durationSeconds = Math.round((Date.now() - activeSession.startTime) / 1000);
    if (durationSeconds >= 1) {
        telemetryQueue.push({
            domain: activeSession.domain,
            duration_seconds: durationSeconds,
            timestamp: new Date().toISOString()
        });
    }
    activeSession.startTime = Date.now();
}

async function updateActiveTab(tabId) {
    flushCurrentSession();
    try {
        const tab = await chrome.tabs.get(tabId);
        const domain = extractDomain(tab.url);
        activeSession = {
            tabId,
            domain,
            startTime: Date.now()
        };
    } catch {
        activeSession = { tabId: null, domain: null, startTime: Date.now() };
    }
}

// Tab switched
chrome.tabs.onActivated.addListener((activeInfo) => {
    updateActiveTab(activeInfo.tabId);
});

// Tab URL changed
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (tabId === activeSession.tabId && changeInfo.url) {
        flushCurrentSession();
        activeSession.domain = extractDomain(changeInfo.url);
        activeSession.startTime = Date.now();
    }
});

// Window focus changed (minimized, switched away)
chrome.windows.onFocusChanged.addListener(async (windowId) => {
    flushCurrentSession();
    if (windowId === chrome.windows.WINDOW_ID_NONE) {
        isUserActive = false;
    } else {
        isUserActive = true;
        const [activeTab] = await chrome.tabs.query({ active: true, windowId });
        if (activeTab) updateActiveTab(activeTab.id);
    }
});

// Idle state detection (child stepped away)
chrome.idle.onStateChanged.addListener((newState) => {
    flushCurrentSession();
    isUserActive = (newState === "active");
    activeSession.startTime = Date.now();
});

// 3. Telemetry & Heartbeat Flush
async function flushTelemetry() {
    flushCurrentSession();
    if (telemetryQueue.length === 0) return;

    const batch = [...telemetryQueue];
    telemetryQueue = [];

    try {
        const apiBase = await getApiBase();
        const deviceToken = await getDeviceToken();

        if (deviceToken) {
            await fetch(`${apiBase}/api/v1/device/telemetry`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${deviceToken}`
                },
                body: JSON.stringify({ visits: batch })
            });
        } else {
            // Legacy batch log
            for (const item of batch) {
                await fetch(`${apiBase}/log`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ site: item.domain, duration: item.duration_seconds })
                });
            }
        }
    } catch (error) {
        console.warn("[SafeNet] Failed to flush telemetry, re-queueing:", error);
        telemetryQueue = [...batch, ...telemetryQueue].slice(-100); // cap buffer
    }
}

async function sendHeartbeat() {
    try {
        const apiBase = await getApiBase();
        const deviceToken = await getDeviceToken();
        if (!deviceToken) return;

        await fetch(`${apiBase}/api/v1/device/heartbeat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${deviceToken}`
            }
        });
    } catch (err) {
        // silent heartbeat fail
    }
}

// 4. Alarms Setup
chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === "sync_policy") {
        await syncPolicy();
    } else if (alarm.name === "flush_telemetry") {
        await flushTelemetry();
        await sendHeartbeat();
    }
});

function initAlarms() {
    chrome.alarms.create("sync_policy", { periodInMinutes: 5 });
    chrome.alarms.create("flush_telemetry", { periodInMinutes: 2 });
}

// 5. Message Dispatcher for Content Script and Popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const handleAsync = async () => {
        const apiBase = await getApiBase();
        const deviceToken = await getDeviceToken();

        switch (message.action) {
            case "getBlocklist": {
                const stored = await chrome.storage.local.get(["blocked_sites"]);
                return { blocked_sites: stored.blocked_sites || [] };
            }

            case "getStatus": {
                const stored = await chrome.storage.local.get(["device_token", "child_info", "blocked_sites", "last_synced"]);
                return {
                    paired: !!stored.device_token,
                    child: stored.child_info || null,
                    rulesCount: (stored.blocked_sites || []).length,
                    lastSynced: stored.last_synced || null
                };
            }

            case "refreshRules": {
                return await syncPolicy();
            }

            case "pairDevice": {
                const code = message.code;
                try {
                    const resp = await fetch(`${apiBase}/api/v1/devices/pair`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ code })
                    });
                    const data = await resp.json();
                    if (resp.ok && data.device_token) {
                        await chrome.storage.local.set({
                            device_token: data.device_token,
                            child_info: data.child
                        });
                        await syncPolicy();
                        return { success: true, child: data.child };
                    } else {
                        return { success: false, error: data.error || "Pairing failed." };
                    }
                } catch (err) {
                    return { success: false, error: err.message };
                }
            }

            case "requestAccess": {
                try {
                    const resp = await fetch(`${apiBase}/api/v1/device/request-access`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": deviceToken ? `Bearer ${deviceToken}` : ""
                        },
                        body: JSON.stringify({
                            url: message.url,
                            reason: message.reason || "School project / Needed access"
                        })
                    });
                    const data = await resp.json();
                    return { success: resp.ok, message: data.message || data.error };
                } catch (err) {
                    return { success: false, error: err.message };
                }
            }

            case "classifyUrl": {
                try {
                    const resp = await fetch(`${apiBase}/api/v1/device/classify`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "Authorization": deviceToken ? `Bearer ${deviceToken}` : ""
                        },
                        body: JSON.stringify({
                            url: message.url,
                            title: message.title,
                            snippet: message.snippet
                        })
                    });
                    return await resp.json();
                } catch (err) {
                    return { blocked: false };
                }
            }

            case "logVisit": {
                if (message.site) {
                    telemetryQueue.push({
                        domain: message.site,
                        duration_seconds: message.duration || 1,
                        timestamp: new Date().toISOString()
                    });
                }
                return { received: true };
            }

            default:
                return { error: "Unknown action" };
        }
    };

    handleAsync().then(sendResponse);
    return true; // Keep message channel open for async response
});

// Initialization
chrome.runtime.onInstalled.addListener(() => {
    initAlarms();
    syncPolicy();
});

chrome.runtime.onStartup.addListener(() => {
    initAlarms();
    syncPolicy();
});
