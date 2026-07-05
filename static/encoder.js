document.addEventListener("DOMContentLoaded", () => {
    const btnBrowse = document.getElementById("btn_browse");
    const videoPathInput = document.getElementById("video_path");
    const btnEncode = document.getElementById("btn_encode");
    const encoderConsole = document.getElementById("encoder_console");
    const encoderForm = document.getElementById("encoderForm");
    
    // Auto-fill configuration
    fetch("/api/config?t=" + new Date().getTime(), { cache: "no-store" })
        .then(res => res.json())
        .then(data => {
            if (data.leds_top) document.getElementById("leds_x").value = data.leds_top;
            if (data.leds_side) document.getElementById("leds_y").value = data.leds_side;
            if (data.led_depth) {
                document.getElementById("depth").value = data.led_depth;
                document.getElementById("depth_val").innerText = data.led_depth + "%";
            }
        });

    btnBrowse.addEventListener("click", () => {
        btnBrowse.textContent = "...";
        fetch("/api/encoder/browse", { method: "POST" })
            .then(res => res.json())
            .then(data => {
                btnBrowse.textContent = "Parcourir...";
                if (data.path) {
                    // Extract filename from the path (handles both / and \)
                    const filename = data.path.split(/[/\\]/).pop();
                    
                    videoPathInput.value = filename;
                    videoPathInput.dataset.fullPath = data.path; // Store full path for the backend
                    
                    // Visual feedback
                    videoPathInput.style.borderColor = "#10b981"; // Green accent
                    videoPathInput.style.backgroundColor = "rgba(16, 185, 129, 0.1)"; // Light green bg
                    videoPathInput.style.color = "#10b981";
                    
                    btnEncode.disabled = false;
                    btnEncode.textContent = "Lancer l'Encodage";
                }
            })
            .catch(err => {
                btnBrowse.textContent = "Parcourir...";
                console.error(err);
            });
    });

    let eventSource = null;

    encoderForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const videoPath = videoPathInput.dataset.fullPath || videoPathInput.value;
        if (!videoPath) return;

        // Reset console
        encoderConsole.textContent = "";
        btnEncode.disabled = true;
        btnEncode.textContent = "Encodage en cours...";
        btnBrowse.disabled = true;
        
        const payload = {
            video_path: videoPath,
            leds_x: parseInt(document.getElementById("leds_x").value),
            leds_y: parseInt(document.getElementById("leds_y").value),
            depth: parseInt(document.getElementById("depth").value),
            threads: parseInt(document.getElementById("threads").value)
        };

        fetch("/api/encoder/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        }).then(res => res.json()).then(data => {
            if (data.status === "success") {
                // Connect to SSE stream
                if (eventSource) eventSource.close();
                eventSource = new EventSource("/api/encoder/stream");
                
                eventSource.onmessage = (event) => {
                    const msgData = JSON.parse(event.data);
                    
                    if (msgData.type === "log") {
                        // Handle progress \r by finding the last \r and replacing current line
                        if (msgData.message.includes('\r')) {
                            const lines = encoderConsole.textContent.split('\n');
                            const parts = msgData.message.split('\r');
                            lines[lines.length - 1] = parts[parts.length - 1];
                            encoderConsole.textContent = lines.join('\n');
                        } else {
                            encoderConsole.textContent += msgData.message;
                        }
                        encoderConsole.scrollTop = encoderConsole.scrollHeight;
                    } 
                    else if (msgData.type === "done") {
                        eventSource.close();
                        btnEncode.disabled = false;
                        btnBrowse.disabled = false;
                        btnEncode.textContent = "Lancer un autre Encodage";
                        encoderConsole.textContent += '\n\n' + msgData.message;
                        encoderConsole.scrollTop = encoderConsole.scrollHeight;
                    }
                };
                
                eventSource.onerror = () => {
                    eventSource.close();
                    btnEncode.disabled = false;
                    btnBrowse.disabled = false;
                    btnEncode.textContent = "Erreur (Réessayer)";
                };
            } else {
                alert("Erreur: " + data.message);
                btnEncode.disabled = false;
                btnBrowse.disabled = false;
                btnEncode.textContent = "Lancer l'Encodage";
            }
        });
    });
});
