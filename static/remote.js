'use strict';

const byId = id => document.getElementById(id);
const video = byId('video');
const canvas = byId('frame');
const context = canvas.getContext('2d', {alpha: false, willReadFrequently: true, colorSpace: 'srgb'});
let session = null;

function stopCapture(message = 'Plex actif') {
    const previous = session;
    session = null;
    if (previous) {
        clearTimeout(previous.watchdog);
        clearTimeout(previous.connectTimer);
        clearInterval(previous.heartbeat);
        previous.reader?.cancel().catch(() => {});
        if (previous.callback !== undefined) video.cancelVideoFrameCallback(previous.callback);
        previous.stream?.getTracks().forEach(track => track.stop());
        previous.socket?.close();
    }
    video.srcObject = null;
    context.clearRect(0, 0, 160, 90);
    byId('start').disabled = false;
    byId('stop').disabled = true;
    byId('state').textContent = message;
    byId('measured-fps').textContent = '0 images/s';
    byId('rtt').textContent = '-';
    byId('processing').textContent = '-';
}

function fail(current, message) {
    if (session !== current) return;
    stopCapture();
    byId('error').textContent = message;
}

function cropRect(width, height) {
    const fraction = id => Math.max(0, Math.min(45, Number(byId(id).value) || 0)) / 100;
    let x = width * fraction('left');
    let y = height * fraction('top');
    let w = width * (1 - fraction('left') - fraction('right'));
    let h = height * (1 - fraction('top') - fraction('bottom'));
    if (byId('center').checked) {
        if (w / h > 16 / 9) {
            const fitted = h * 16 / 9;
            x += (w - fitted) / 2;
            w = fitted;
        } else {
            const fitted = w * 9 / 16;
            y += (h - fitted) / 2;
            h = fitted;
        }
    }
    return [x, y, w, h];
}

function onFrame(current, now) {
    if (session !== current) return;
    current.callback = video.requestVideoFrameCallback(timestamp => onFrame(current, timestamp));
    sendFrame(current, video, video.videoWidth, video.videoHeight, now);
}

async function readFrames(current) {
    try {
        while (session === current) {
            const {value: frame, done} = await current.reader.read();
            if (done) {
                if (session === current) fail(current, 'Le flux de capture est terminé.');
                return;
            }
            try {
                if (session === current) {
                    sendFrame(current, frame, frame.displayWidth, frame.displayHeight, performance.now());
                }
            } finally {
                frame.close();
            }
        }
    } catch (error) {
        fail(current, error.message);
    }
}

function sendFrame(current, source, width, height, now) {
    const interval = 1000 / Number(byId('fps').value);
    if (!current.ready || current.pending || current.socket.readyState !== WebSocket.OPEN
        || current.socket.bufferedAmount || now - current.lastFrame < interval - 2) return;
    try {
        context.drawImage(source, ...cropRect(width, height), 0, 0, 160, 90);
        const rgba = context.getImageData(0, 0, 160, 90).data;
        current.pending = true;
        current.sentAt = performance.now();
        current.lastFrame = now;
        current.socket.send(rgba);
        current.watchdog = setTimeout(() => fail(current, 'Le serveur ne répond plus.'), 3000);
    } catch (error) {
        fail(current, error.message);
    }
}

byId('start').addEventListener('click', async () => {
    byId('error').textContent = '';
    if (!navigator.mediaDevices?.getDisplayMedia
        || (!window.MediaStreamTrackProcessor && !video.requestVideoFrameCallback)) {
        byId('error').textContent = 'Capture indisponible. Ouvre http://localhost:5777/remote dans Chrome ou Edge sur le PC AmbiPlex.';
        return;
    }
    const current = {pending: false, ready: false, lastFrame: -Infinity, count: 0, measuredAt: performance.now()};
    session = current;
    byId('start').disabled = true;
    byId('stop').disabled = false;
    byId('state').textContent = 'Sélection de la source';
    try {
        const stream = await navigator.mediaDevices.getDisplayMedia({
            video: {displaySurface: 'browser', frameRate: {ideal: 60, max: 60}},
            audio: false, selfBrowserSurface: 'exclude', surfaceSwitching: 'exclude',
        });
        if (session !== current) {
            stream.getTracks().forEach(track => track.stop());
            return;
        }
        current.stream = stream;
        stream.getVideoTracks()[0].addEventListener('ended', () => {
            if (session === current) stopCapture();
        });
        if (window.MediaStreamTrackProcessor) {
            // Consume capture frames independently of video rendering/visibility.
            current.reader = new MediaStreamTrackProcessor({
                track: stream.getVideoTracks()[0], maxBufferSize: 1,
            }).readable.getReader();
        } else {
            video.srcObject = stream;
            await video.play();
        }
        if (session !== current) return;
        const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/remote/frames`);
        current.socket = socket;
        current.connectTimer = setTimeout(() => fail(current, 'Connexion au serveur impossible.'), 5000);
        socket.onmessage = event => {
            if (session !== current) return;
            const data = JSON.parse(event.data);
            if (data.type === 'ready') {
                clearTimeout(current.connectTimer);
                current.ready = true;
                current.heartbeat = setInterval(() => {
                    if (session === current && socket.readyState === WebSocket.OPEN
                        && !current.pending && !socket.bufferedAmount) socket.send('ping');
                }, 1000);
                byId('state').textContent = 'Remote Play actif';
            } else if (data.type === 'frame') {
                clearTimeout(current.watchdog);
                current.pending = false;
                byId('rtt').textContent = `${(performance.now() - current.sentAt).toFixed(1)} ms`;
                byId('processing').textContent = `${data.processing_ms.toFixed(1)} ms`;
                current.count++;
                const elapsed = performance.now() - current.measuredAt;
                if (elapsed >= 1000) {
                    byId('measured-fps').textContent = `${Math.round(current.count * 1000 / elapsed)} images/s`;
                    current.count = 0;
                    current.measuredAt = performance.now();
                }
            }
        };
        socket.onerror = () => fail(current, 'Connexion locale interrompue.');
        socket.onclose = event => fail(current, event.reason || `Capture déconnectée (code ${event.code}).`);
        if (current.reader) {
            readFrames(current);
        } else {
            current.callback = video.requestVideoFrameCallback(timestamp => onFrame(current, timestamp));
        }
    } catch (error) {
        fail(current, error.name === 'NotAllowedError' ? 'Partage annulé ou refusé.' : error.message);
    }
});

byId('stop').addEventListener('click', () => stopCapture());
window.addEventListener('pagehide', () => stopCapture());
byId('back-plex').addEventListener('click', event => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) {
        stopCapture();
    }
});
