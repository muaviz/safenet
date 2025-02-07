document.addEventListener("DOMContentLoaded", function () {
    console.log("DOM fully loaded!"); // Debugging

    const form = document.getElementById("block-website-form");
    const inputField = document.getElementById("website-url");
    const blockedWebsitesList = document.getElementById("blocked-websites-list");

    if (!form) {
        console.error("Form not found!");
        return;
    }
    if (!inputField) {
        console.error("Input field not found!");
        return;
    }

    console.log("Form and input field found!"); // Debugging

    form.addEventListener("submit", async function (event) {
        event.preventDefault(); // Prevents page reload
        console.log("Form submitted!"); // Debugging

        const url = inputField.value.trim();
        console.log("Captured URL:", url); // Debugging

        if (!url) {
            alert("Please enter a website URL.");
            return;
        }

        try {
            const response = await fetch("http://localhost:5000/blocklist", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url })
            });

            const data = await response.json();
            console.log("Server response:", data);

            if (response.ok) {
                // Display the newly blocked website in the list
                const listItem = document.createElement("div");
                listItem.textContent = url;
                listItem.classList.add("bg-red-100", "text-red-700", "px-4", "py-2", "rounded-lg");

                blockedWebsitesList.appendChild(listItem);
                inputField.value = ""; // Clear input field
            } else {
                alert(data.message || "Error blocking site");
            }
        } catch (error) {
            console.error("Error:", error);
        }
    });
});
    