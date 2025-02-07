// Log visits by sending a message to the background script
chrome.runtime.sendMessage({ action: "logVisit", site: window.location.hostname });

// Request blocklist from the background script
chrome.runtime.sendMessage({ action: "getBlocklist" }, (blocklist) => {
    if (chrome.runtime.lastError) {
        console.error("Error fetching blocklist:", chrome.runtime.lastError);
        return;
    }

    console.log("Received blocklist:", blocklist);

    // Check if the current site (or its subdomain) is in the blocklist
    const currentHost = window.location.hostname.toLowerCase();

    const isBlocked = blocklist.some(blockedSite => 
        currentHost === blockedSite || currentHost.endsWith(`.${blockedSite}`)
    );

    if (isBlocked) {
        console.warn(`Blocking access to: ${currentHost}`);
        window.location.replace(chrome.runtime.getURL("blockPage.html"));
    }    
});
