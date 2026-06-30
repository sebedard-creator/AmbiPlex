document.addEventListener("DOMContentLoaded", () => {
    let currentPresets = {};

    // Load config
    fetch("/api/config")
        .then(res => res.json())
        .then(data => {
            document.getElementById("plex_url").value = data.plex_url || "http://127.0.0.1:32400";
            document.getElementById("plex_token").value = data.plex_token || "";
            document.getElementById("master_client").value = data.master_client || "Sony Bravia";
            document.getElementById("headless").checked = data.headless !== false;
            
            // LED config
            if(document.getElementById("wled_ip")) {
                document.getElementById("wled_ip").value = data.wled_ip || "";
                document.getElementById("leds_top").value = data.leds_top || 50;
                document.getElementById("leds_side").value = data.leds_side || 30;
                document.getElementById("led_depth").value = data.led_depth || 8;
                document.getElementById("led_depth_val").innerText = (data.led_depth || 8) + "%";
                document.getElementById("led_smoothing").value = data.led_smoothing || 65;
                document.getElementById("led_smoothing_val").innerText = (data.led_smoothing || 65) + "%";
                if(document.getElementById("led_brightness")) {
                    document.getElementById("led_brightness").value = data.led_brightness || 80;
                    document.getElementById("led_brightness_val").innerText = (data.led_brightness || 80) + "%";
                }
                if(document.getElementById("led_refresh_rate")) {
                    document.getElementById("led_refresh_rate").value = data.led_refresh_rate || 20;
                    document.getElementById("led_refresh_native").checked = data.led_refresh_native || false;
                    document.getElementById("led_refresh_rate_val").innerText = data.led_refresh_native ? "Natif" : (data.led_refresh_rate || 20);
                }
                
                // Dessiner le simulateur (avec ou sans couleurs) pour afficher les numéros immédiatement
                drawSimulator([]);
            }

            currentPresets = data.presets || {};
            if (data.current_preset && currentPresets[data.current_preset] !== undefined) {
                const select = document.getElementById("preset_select");
                select.innerHTML = '';
                select.add(new Option(data.current_preset, data.current_preset));
                select.value = data.current_preset;
                
                // Mettre à jour l'input avec la valeur du preset actif !
                document.getElementById("sync_offset").value = currentPresets[data.current_preset];
                
                // Activer les contrôles
                document.getElementById("sync_offset").disabled = false;
                const btnSave = document.getElementById("btn_save");
                if(btnSave) {
                    btnSave.disabled = false;
                    btnSave.style.opacity = 1;
                    btnSave.style.cursor = "pointer";
                    btnSave.textContent = "Sauvegarder la Calibration";
                }
            } else {
                document.getElementById("sync_offset").value = data.sync_offset_frames || 0;
            }
        });

    // Handle form submit
    document.getElementById("configForm").addEventListener("submit", (e) => {
        e.preventDefault();
        
        const presetName = document.getElementById("preset_select").value;
        const newOffset = parseInt(document.getElementById("sync_offset").value) || 0;
        
        if (presetName && presetName !== "") {
            currentPresets[presetName] = newOffset;
        }

        const config = {
            plex_url: document.getElementById("plex_url").value,
            plex_token: document.getElementById("plex_token").value,
            master_client: document.getElementById("master_client").value,
            headless: document.getElementById("headless").checked,
            sync_offset_frames: newOffset,
            presets: currentPresets,
            current_preset: presetName || "",
            wled_ip: document.getElementById("wled_ip") ? document.getElementById("wled_ip").value : "",
            leds_top: document.getElementById("leds_top") ? parseInt(document.getElementById("leds_top").value) || 50 : 50,
            leds_side: document.getElementById("leds_side") ? parseInt(document.getElementById("leds_side").value) || 30 : 30,
            led_depth: document.getElementById("led_depth") ? parseInt(document.getElementById("led_depth").value) || 8 : 8,
            led_smoothing: document.getElementById("led_smoothing") ? parseInt(document.getElementById("led_smoothing").value) || 65 : 65,
            led_brightness: document.getElementById("led_brightness") ? parseInt(document.getElementById("led_brightness").value) || 80 : 80
        };

        fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        }).then(res => res.json()).then(data => {
            if(data.status === "success") {
                const msg = document.getElementById("saveMsg");
                msg.classList.remove("hidden");
                setTimeout(() => msg.classList.add("hidden"), 3000);
            }
        });
    });

    // Handle LED form submit
    const ledForm = document.getElementById("ledForm");
    if (ledForm) {
        ledForm.addEventListener("submit", (e) => {
            e.preventDefault();
            
            // Rebuild config with new LED values
            const config = {
                plex_url: document.getElementById("plex_url").value,
                plex_token: document.getElementById("plex_token").value,
                master_client: document.getElementById("master_client").value,
                headless: document.getElementById("headless").checked,
                sync_offset_frames: parseInt(document.getElementById("sync_offset").value) || 0,
                presets: currentPresets,
                current_preset: document.getElementById("preset_select").value || "",
                wled_ip: document.getElementById("wled_ip").value,
                leds_top: parseInt(document.getElementById("leds_top").value) || 50,
                leds_side: parseInt(document.getElementById("leds_side").value) || 30,
                led_depth: parseInt(document.getElementById("led_depth").value) || 8,
                led_smoothing: parseInt(document.getElementById("led_smoothing").value) || 65,
                led_brightness: parseInt(document.getElementById("led_brightness").value) || 80,
                led_refresh_rate: parseInt(document.getElementById("led_refresh_rate").value) || 20,
                led_refresh_native: document.getElementById("led_refresh_native").checked
            };

            fetch("/api/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(config)
            }).then(res => res.json()).then(data => {
                if(data.status === "success") {
                    const btn = ledForm.querySelector('button');
                    const oldText = btn.textContent;
                    btn.textContent = "✓ Calibration Appliquée";
                    btn.style.background = "#2ea043";
                    setTimeout(() => {
                        btn.textContent = oldText;
                        btn.style.background = "";
                    }, 2000);
                }
            });
        });
    }

    // Server Sent Events for Monitoring
    const evtSource = new EventSource("/api/stream");
    const consoleEl = document.getElementById("console");
    
    function logToConsole(msg, type="info") {
        if (consoleEl.textContent.includes("En attente de connexion")) {
            consoleEl.innerHTML = "";
        }
        const div = document.createElement("div");
        div.className = `log ${type}`;
        const time = new Date().toLocaleTimeString();
        div.textContent = `[${time}] ${msg}`;
        consoleEl.appendChild(div);
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }

    const canvas = document.getElementById("ledSimulator");
    const ctx = canvas ? canvas.getContext("2d") : null;

    evtSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        if(data.type === "info") {
            const el = document.createElement("div");
            el.className = "log";
            el.textContent = `[INFO] ${data.message}`;
            consoleEl.appendChild(el);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        } else if (data.type === "preset_changed") {
            // Mettre à jour silencieusement l'UI
            const select = document.getElementById("preset_select");
            if(select.options.length > 0 && select.options[0].value === "") {
                select.innerHTML = '';
            }
            if(!Array.from(select.options).some(o => o.value === data.combo)) {
                select.add(new Option(data.combo, data.combo));
            }
            select.value = data.combo;
            
            document.getElementById("sync_offset").value = data.offset_frames;
            document.getElementById("sync_offset").disabled = false;
            
            const btnSave = document.getElementById("btn_save");
            if(btnSave) {
                btnSave.disabled = false;
                btnSave.style.opacity = 1;
                btnSave.style.cursor = "pointer";
                btnSave.textContent = "Sauvegarder la Calibration";
            }
            
            if(currentPresets[data.combo] === undefined) {
                currentPresets[data.combo] = data.offset_frames;
            }
            
        } else if(data.type === "monitoring") {
            document.getElementById("status_state").textContent = data.state.toUpperCase();
            document.getElementById("status_state").className = "badge " + (data.state === "playing" ? "playing" : "paused");
            
            document.getElementById("status_offset").textContent = data.offset + " ms";
            document.getElementById("status_local_offset").textContent = Math.round(data.local_offset) + " ms";
            document.getElementById("status_action").textContent = data.action;
            if(document.getElementById("status_dropped") && data.dropped_frames !== undefined) {
                document.getElementById("status_dropped").textContent = data.dropped_frames;
            }
            if(document.getElementById("status_crop") && data.crop_box) {
                document.getElementById("status_crop").textContent = `${data.crop_box[0]} à ${data.crop_box[1]}`;
            }
            
            // Dessiner la simulation LED
            if(data.colors && ctx) {
                drawSimulator(data.colors);
            }
        }
    };

    function drawSimulator(colors) {
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        
        const ledsTop = parseInt(document.getElementById("leds_top").value) || 50;
        const ledsSide = parseInt(document.getElementById("leds_side").value) || 30;
        
        const totalTop = ledsTop;
        const totalRight = ledsSide;
        const totalBottom = ledsTop;
        const totalLeft = ledsSide;
        
        const hasColors = colors && colors.length >= (totalTop + totalRight + totalBottom + totalLeft);
        
        let cIdx = 0;
        const thickness = 8;
        
        // Background TV
        ctx.fillStyle = "#111";
        ctx.fillRect(thickness, thickness, w - thickness*2, h - thickness*2);
        
        if (hasColors) {
        
        // 1. Top (gauche -> droite)
        if(totalTop > 0) {
            const segW = w / totalTop;
            for(let i=0; i<totalTop; i++) {
                const c = colors[cIdx++];
                ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
                ctx.shadowColor = ctx.fillStyle;
                ctx.shadowBlur = 15;
                ctx.fillRect(i * segW, 0, segW+1, thickness);
            }
        }
        
        // 2. Right (haut -> bas)
        if(totalRight > 0) {
            const segH = h / totalRight;
            for(let i=0; i<totalRight; i++) {
                const c = colors[cIdx++];
                ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
                ctx.shadowColor = ctx.fillStyle;
                ctx.shadowBlur = 15;
                ctx.fillRect(w - thickness, i * segH, thickness, segH+1);
            }
        }
        
        // 3. Bottom (droite -> gauche)
        if(totalBottom > 0) {
            const segW = w / totalBottom;
            for(let i=totalBottom-1; i>=0; i--) {
                const c = colors[cIdx++];
                ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
                ctx.shadowColor = ctx.fillStyle;
                ctx.shadowBlur = 15;
                ctx.fillRect(i * segW, h - thickness, segW+1, thickness);
            }
        }
        
        // 4. Left (bas -> haut)
        if(totalLeft > 0) {
            const segH = h / totalLeft;
            for(let i=totalLeft-1; i>=0; i--) {
                const c = colors[cIdx++];
                ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
                ctx.shadowColor = ctx.fillStyle;
                ctx.shadowBlur = 15;
                ctx.fillRect(0, i * segH, thickness, segH+1);
            }
        }
        } // End of hasColors check
        ctx.shadowBlur = 0; // reset
        
        // --- Draw LED Numbers ---
        ctx.font = "10px 'Inter', 'Segoe UI', Arial, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        const drawLabel = (text, x, y, isCorner) => {
            const padX = 5;
            const padY = 3;
            const textWidth = ctx.measureText(text).width;
            const textHeight = 10;
            
            ctx.fillStyle = isCorner ? "rgba(52, 152, 219, 0.95)" : "rgba(30, 30, 30, 0.75)";
            if (ctx.roundRect) {
                ctx.beginPath();
                ctx.roundRect(x - textWidth/2 - padX, y - textHeight/2 - padY, textWidth + padX*2, textHeight + padY*2, 4);
                ctx.fill();
            } else {
                ctx.fillRect(x - textWidth/2 - padX, y - textHeight/2 - padY, textWidth + padX*2, textHeight + padY*2);
            }
            
            ctx.fillStyle = "#ffffff";
            ctx.fillText(text, x, y + 1);
        };

        const totalLeds = totalTop + totalRight + totalBottom + totalLeft;
        for (let idx = 0; idx < totalLeds; idx++) {
            const num = idx + 1;
            let isCorner = false;
            let shouldDraw = false;
            
            // Define exactly the corner LEDs (We remove totalLeds to avoid overlapping LED 1)
            if (num === 1 || num === totalTop || num === totalTop + totalRight || num === totalTop + totalRight + totalBottom) {
                isCorner = true;
                shouldDraw = true;
            } else if (num % 10 === 0) {
                // Avoid overlapping multiples of 10 if they are too close to a corner
                const d1 = Math.abs(num - 1);
                const d2 = Math.abs(num - totalTop);
                const d3 = Math.abs(num - (totalTop + totalRight));
                const d4 = Math.abs(num - (totalTop + totalRight + totalBottom));
                const d5 = Math.abs(num - totalLeds);
                
                // Increase margin to 6 to prevent physical overlap on short edges
                if (d1 > 6 && d2 > 6 && d3 > 6 && d4 > 6 && d5 > 6) {
                    shouldDraw = true;
                }
            }

            if (shouldDraw) {
                let x = 0, y = 0;
                let offset = 26; // Distance from the border

                if (num === 1) {
                    x = offset; y = offset;
                } else if (num === totalTop) {
                    x = w - offset; y = offset;
                } else if (num === totalTop + totalRight) {
                    x = w - offset; y = h - offset;
                } else if (num === totalTop + totalRight + totalBottom) {
                    x = offset; y = h - offset;
                } else {
                    if (idx < totalTop) {
                        x = (idx * (w / totalTop)) + ((w / totalTop) / 2);
                        y = offset;
                    } else if (idx < totalTop + totalRight) {
                        let sideIdx = idx - totalTop;
                        x = w - offset;
                        y = (sideIdx * (h / totalRight)) + ((h / totalRight) / 2);
                    } else if (idx < totalTop + totalRight + totalBottom) {
                        let botIdx = idx - (totalTop + totalRight);
                        x = w - (botIdx * (w / totalBottom)) - ((w / totalBottom) / 2);
                        y = h - offset;
                    } else {
                        let leftIdx = idx - (totalTop + totalRight + totalBottom);
                        x = offset;
                        y = h - (leftIdx * (h / totalLeft)) - ((h / totalLeft) / 2);
                    }
                }

                // Clamp coordinates on ALL axes to prevent any text from being cut off
                const padX = 5, padY = 3;
                const textWidth = ctx.measureText(num.toString()).width;
                const textHeight = 10;
                
                const safeX = textWidth / 2 + padX + 2;
                const safeY = textHeight / 2 + padY + 2;
                
                x = Math.max(safeX, Math.min(w - safeX, x));
                y = Math.max(safeY, Math.min(h - safeY, y));

                drawLabel(num.toString(), x, y, isCorner);
            }
        }
    }

    // Fermer proprement la connexion SSE quand on quitte la page (évite la limite de 6 connexions du navigateur)
    window.addEventListener('beforeunload', () => {
        if(evtSource) evtSource.close();
    });
});

// Reset values to safe defaults
window.resetSliders = function() {
    if(document.getElementById("led_depth")) {
        document.getElementById("led_depth").value = 8;
        document.getElementById("led_depth_val").innerText = "8%";
    }
    if(document.getElementById("led_smoothing")) {
        document.getElementById("led_smoothing").value = 65;
        document.getElementById("led_smoothing_val").innerText = "65%";
    }
    if(document.getElementById("led_brightness")) {
        document.getElementById("led_brightness").value = 80;
        document.getElementById("led_brightness_val").innerText = "80%";
    }
    if(document.getElementById("led_refresh_rate")) {
        document.getElementById("led_refresh_rate").value = 20;
        document.getElementById("led_refresh_native").checked = false;
        document.getElementById("led_refresh_rate_val").innerText = "20";
    }
};
