const API_BASE_URL = "http://localhost:5000";  // Flask backend URL
const BLOCK_PAGE_URL = chrome.runtime.getURL("blockPage.html");

// Fetch blocklist and update extension rules
async function updateBlocklist() {
    try {
        const response = await fetch(`${API_BASE_URL}/blocklist`);
        const data = await response.json();
        const blocklist = data.blocked_sites || [];

        // Generate rule IDs for blocked sites
        const ruleIds = blocklist.map((_, index) => index + 1);

        // Remove all previous rules
        chrome.declarativeNetRequest.updateDynamicRules({
            removeRuleIds: ruleIds,
            addRules: [] // Remove all previous rules first
        }, () => {
            // Now add the updated rules
            const rules = blocklist.map((site, index) => ({
                id: index + 1, 
                priority: 1,
                action: { type: "redirect", redirect: { url: BLOCK_PAGE_URL } },
                condition: {
                    urlFilter: site, 
                    resourceTypes: ["main_frame"]
                }
            }));

            chrome.declarativeNetRequest.updateDynamicRules({
                addRules: rules
            }, () => console.log("Updated blocklist:", rules));
        });

    } catch (error) {
        console.error("Failed to fetch blocklist:", error);
    }
}

// Fetch and update blocklist on startup
chrome.runtime.onInstalled.addListener(updateBlocklist);
chrome.runtime.onStartup.addListener(updateBlocklist);

// Periodically refresh the blocklist (every 5 minutes)
setInterval(updateBlocklist, 5 * 60 * 1000);
