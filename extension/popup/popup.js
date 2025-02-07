document.getElementById("refreshBlocklist").addEventListener("click", async () => {
    try {
        const response = await fetch("http://localhost:5000/blocklist");
        const data = await response.json();
        alert(`Blocklist updated! ${data.blocked_sites.length} sites blocked.`);
    } catch (error) {
        alert("Failed to update blocklist.");
    }
});
