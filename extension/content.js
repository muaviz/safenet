// SafeNet Extension - Content Script
(function () {
    const currentHost = window.location.hostname.toLowerCase().replace(/^www\./, '');

    // 1. Check local blocklist fallback
    chrome.runtime.sendMessage({ action: "getBlocklist" }, (response) => {
        if (chrome.runtime.lastError || !response || !response.blocked_sites) {
            return;
        }

        const blocklist = response.blocked_sites;
        const isBlocked = blocklist.some(blockedSite => {
            const clean = blockedSite.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
            return currentHost === clean || currentHost.endsWith(`.${clean}`);
        });

        if (isBlocked) {
            console.warn(`[SafeNet] Content script blocking access to: ${currentHost}`);
            window.location.replace(chrome.runtime.getURL(`blockPage.html?blocked=${encodeURIComponent(currentHost)}`));
        }
    });

    // 2. Extract metadata for AI / Heuristic analysis (run only on main pages)
    if (window.top === window.self && document.body) {
        const pageTitle = document.title || "";
        const metaDesc = document.querySelector('meta[name="description"]')?.getAttribute("content") || "";
        const bodySnippet = document.body.innerText ? document.body.innerText.substring(0, 500) : "";

        // Send for content analysis if text contains suspicious patterns or uncataloged site
        chrome.runtime.sendMessage({
            action: "classifyUrl",
            url: window.location.href,
            title: pageTitle,
            snippet: `${metaDesc} ${bodySnippet}`.trim()
        }, (response) => {
            if (!chrome.runtime.lastError && response && response.blocked) {
                console.warn(`[SafeNet] Real-time AI classified page as blocked: ${response.reason || 'Safety policy'}`);
                window.location.replace(chrome.runtime.getURL(`blockPage.html?blocked=${encodeURIComponent(currentHost)}&reason=${encodeURIComponent(response.reason || 'Inappropriate content')}`));
            }
        });
    }
})();
