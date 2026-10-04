// TrustLens Service Worker (Manifest V3)
chrome.runtime.onInstalled.addListener(() => {
  console.log("TrustLens Service Worker initialized.");
});

// Relay messages between content script / popup and backend API
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ANALYZE_PRODUCT") {
    const backendUrl = "http://localhost:8000/predict";
    fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(request.payload)
    })
      .then(response => {
        if (!response.ok) {
          throw new Error(`Backend returned status ${response.status}`);
        }
        return response.json();
      })
      .then(data => sendResponse({ success: true, data: data }))
      .catch(error => {
        console.error("TrustLens API error:", error);
        sendResponse({ success: false, error: error.message });
      });

    return true; // Keep channel open for async fetch
  }
});
