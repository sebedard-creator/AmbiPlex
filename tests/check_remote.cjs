const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const root = path.resolve(__dirname, '..');
    const port = 18000 + Math.floor(Math.random() * 10000);
    const base = `http://127.0.0.1:${port}`;
    const server = spawn(process.env.PYTHON || path.join(root, 'venv', 'Scripts', 'python.exe'),
        ['-B', 'tests/test_remote_capture.py', '--serve', String(port)], {cwd: root, windowsHide: true});
    let output = '';
    server.stderr.on('data', chunk => { output += chunk; });
    const exited = new Promise(resolve => server.on('exit', resolve));
    let browser;
    try {
        let ready = false;
        for (let attempt = 0; attempt < 100; attempt++) {
            try { ready = (await fetch(`${base}/test-stats`)).ok; } catch {}
            if (ready) break;
            if (server.exitCode !== null) throw Error(output);
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        assert(ready, output || 'Fixture did not start');
        browser = await chromium.launch({headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome'});
        const page = await browser.newPage({viewport: {width: 1280, height: 900}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.addInitScript(() => {
            window.captureMode = 'normal';
            window.pauseHeartbeatTimer = false;
            window.serverProbes = 0;
            const interval = window.setInterval.bind(window);
            window.setInterval = (callback, delay, ...args) => interval(() => {
                if (delay !== 1000 || !window.pauseHeartbeatTimer) callback(...args);
            }, delay);
            const Socket = window.WebSocket;
            window.WebSocket = class extends Socket {
                constructor(...args) {
                    super(...args);
                    this.addEventListener('message', event => {
                        if (JSON.parse(event.data).type === 'ping') window.serverProbes++;
                    });
                }
            };
            window.renderFrameCallback = HTMLVideoElement.prototype.requestVideoFrameCallback;
            HTMLVideoElement.prototype.requestVideoFrameCallback = () => {
                throw Error('Rendering callbacks must not be used by the direct capture path');
            };
            navigator.mediaDevices.getDisplayMedia = async options => {
                window.captureOptions = options;
                if (window.captureMode === 'deny') throw new DOMException('Denied', 'NotAllowedError');
                if (window.captureMode === 'unreadable') throw new DOMException('Unreadable', 'NotReadableError');
                const ps4 = options.video.displaySurface === 'window';
                const width = ps4 ? 960 : 1280;
                const height = ps4 ? 540 : 720;
                const toolbar = window.captureMode === 'decorated' ? 60 : 0;
                const source = document.createElement('canvas');
                source.width = width;
                source.height = height + toolbar;
                const ctx = source.getContext('2d');
                let tick = 0;
                const draw = () => {
                    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, width, toolbar);
                    ctx.fillStyle = '#e02020'; ctx.fillRect(0, toolbar, width / 2, height / 2);
                    ctx.fillStyle = '#20d040'; ctx.fillRect(width / 2, toolbar, width / 2, height / 2);
                    ctx.fillStyle = '#2040e0'; ctx.fillRect(0, toolbar + height / 2, width / 2, height / 2);
                    ctx.fillStyle = '#e0c020'; ctx.fillRect(width / 2, toolbar + height / 2, width / 2, height / 2);
                    ctx.fillStyle = tick++ % 2 ? '#fff' : '#888'; ctx.fillRect(width / 2 - 20, toolbar + height / 2 - 20, 40, 40);
                };
                draw();
                let timer = setInterval(draw, 16);
                window.freezeTestInput = () => clearInterval(timer);
                window.resumeTestInput = () => { timer = setInterval(draw, 16); };
                const stream = source.captureStream(60);
                const track = stream.getVideoTracks()[0];
                const getSettings = track.getSettings.bind(track);
                track.getSettings = () => ({...getSettings(), displaySurface: ps4 ? 'window' : 'browser'});
                const stop = track.stop.bind(track);
                track.stop = () => { clearInterval(timer); stop(); };
                window.testStream = stream;
                window.endTestTrack = () => {
                    stream.getVideoTracks()[0].dispatchEvent(new Event('ended'));
                    clearInterval(timer);
                };
                return stream;
            };
        });
        await page.goto(`${base}/remote`);
        assert.equal(await page.locator('#source').inputValue(), 'xbox');
        assert(await page.locator('#launch-chiaki').isHidden());
        assert.equal((await fetch(`${base}/api/remote/chiaki/start`)).status, 405);
        assert.equal((await fetch(`${base}/api/remote/chiaki/start`, {
            method: 'POST', headers: {Origin: 'https://evil.example'},
        })).status, 403);
        assert.equal((await (await fetch(`${base}/test-stats`)).json()).launches, 0);
        await page.locator('#source').selectOption('ps4');
        assert(await page.locator('#launch-chiaki').isVisible());
        await page.locator('#launch-chiaki').click();
        await page.waitForFunction(() => document.getElementById('chiaki-status').textContent === 'Chiaki lancé.');
        assert.equal((await (await fetch(`${base}/test-stats`)).json()).launches, 1);
        assert.equal(await page.evaluate(() => window.captureOptions), undefined);
        assert(await page.locator('#launch-chiaki').isEnabled());
        await page.route('**/api/remote/chiaki/start', route => route.fulfill({
            status: 404, json: {detail: 'Chiaki introuvable.'},
        }));
        await page.locator('#launch-chiaki').click();
        await page.waitForFunction(() => document.getElementById('chiaki-status').textContent === 'Chiaki introuvable.');
        assert(await page.locator('#launch-chiaki').isEnabled());
        await page.unroute('**/api/remote/chiaki/start');
        await page.locator('#source').selectOption('xbox');
        assert(await page.locator('#chiaki-status').isHidden());
        assert(await page.locator('#stop').isDisabled());
        await page.locator('#start').click();
        await page.waitForFunction(() => document.getElementById('state').textContent === 'Remote Play actif');
        for (let i = 0; i < 100; i++) {
            const stats = await (await fetch(`${base}/test-stats`)).json();
            if (stats.frames >= 10) break;
            await page.waitForTimeout(50);
        }
        const stats = await (await fetch(`${base}/test-stats`)).json();
        assert(stats.frames >= 10);
        assert.equal(stats.colors.length, 200);
        assert.deepEqual(stats.colors[0], [224, 32, 32]);
        assert.deepEqual(stats.colors[63], [32, 208, 64]);
        const pixel = await page.locator('#frame').evaluate(canvas =>
            [...canvas.getContext('2d').getImageData(10, 10, 1, 1).data]);
        assert.deepEqual(pixel, [224, 32, 32, 255]);
        assert.equal(await page.locator('#source-size').textContent(), '1280 × 720');
        assert.equal(await page.locator('#capture-surface').textContent(), 'Onglet');
        assert.equal(await page.evaluate(() => window.captureOptions.video.displaySurface), 'browser');
        assert(await page.locator('#source').isDisabled());
        await page.evaluate(() => window.freezeTestInput());
        await page.waitForTimeout(6000);
        assert.equal((await (await fetch(`${base}/test-stats`)).json()).active, true);
        assert.equal(await page.locator('#state').textContent(), 'Remote Play actif');
        const desktop = path.join(os.tmpdir(), 'ambiplex-remote-desktop.png');
        await page.screenshot({path: desktop});
        await page.setViewportSize({width: 390, height: 844});
        await page.screenshot({path: path.join(os.tmpdir(), 'ambiplex-remote-mobile.png')});
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.locator('#stop').click();
        await page.waitForFunction(() => window.testStream.getTracks().every(track => track.readyState === 'ended'));
        for (let i = 0; i < 50 && (await (await fetch(`${base}/test-stats`)).json()).active; i++) {
            await page.waitForTimeout(20);
        }
        assert.equal((await (await fetch(`${base}/test-stats`)).json()).active, false);
        assert(await page.locator('#source').isEnabled());
        assert.equal(await page.locator('#source-size').textContent(), '-');

        // Same colors from a 540p app window, with and without a captured toolbar.
        await page.setViewportSize({width: 1280, height: 900});
        for (const decorated of [false, true]) {
            await page.goto(`${base}/remote?source=ps4`);
            assert.equal(await page.locator('#source').inputValue(), 'ps4');
            assert.equal(await page.locator('#source option:checked').textContent(), 'PlayStation Remote Play');
            if (decorated) {
                await page.evaluate(() => { window.captureMode = 'decorated'; });
                await page.locator('#top').fill('10');
            }
            const before = (await (await fetch(`${base}/test-stats`)).json()).frames;
            await page.locator('#start').click();
            await page.waitForFunction(() => document.getElementById('state').textContent === 'Remote Play actif');
            let captured;
            for (let i = 0; i < 100; i++) {
                captured = await (await fetch(`${base}/test-stats`)).json();
                if (captured.frames >= before + 3) break;
                await page.waitForTimeout(50);
            }
            assert(captured.frames >= before + 3);
            assert.deepEqual(captured.colors, stats.colors, '540p PS4 window must preserve all LED colors');
            assert.equal(await page.locator('#source-size').textContent(), decorated ? '960 × 600' : '960 × 540');
            assert.equal(await page.locator('#capture-surface').textContent(), 'Fenêtre');
            const options = await page.evaluate(() => window.captureOptions);
            assert.equal(options.video.displaySurface, 'window');
            assert.equal(options.audio, false);
            assert.equal(options.video.width, undefined);
            assert.equal(options.video.height, undefined);
            assert.deepEqual(options.video.frameRate, {ideal: 60, max: 60});
            assert(await page.locator('#source').isDisabled());
            assert(await page.locator('#launch-chiaki').isDisabled());
            if (!decorated) {
                // Simulate a hidden page's heartbeat timer stopping, with no new source frames.
                await page.evaluate(() => {
                    window.pauseHeartbeatTimer = true;
                    window.freezeTestInput();
                });
                await page.waitForTimeout(17000);
                assert.equal((await (await fetch(`${base}/test-stats`)).json()).active, true);
                assert.equal(await page.locator('#state').textContent(), 'Remote Play actif');
                assert(await page.evaluate(() => window.serverProbes >= 2));
                const pausedFrames = (await (await fetch(`${base}/test-stats`)).json()).frames;
                await page.evaluate(() => {
                    window.pauseHeartbeatTimer = false;
                    window.resumeTestInput();
                });
                for (let i = 0; i < 100; i++) {
                    if ((await (await fetch(`${base}/test-stats`)).json()).frames > pausedFrames) break;
                    await page.waitForTimeout(50);
                }
                const resumed = await (await fetch(`${base}/test-stats`)).json();
                assert(resumed.frames > pausedFrames);
                assert.deepEqual(resumed.colors, stats.colors);
                await page.screenshot({path: path.join(os.tmpdir(), 'ambiplex-ps4-desktop.png')});
                await page.setViewportSize({width: 390, height: 844});
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
                await page.screenshot({path: path.join(os.tmpdir(), 'ambiplex-ps4-mobile.png'), fullPage: true});
                await page.setViewportSize({width: 1280, height: 900});
            }
            await page.locator('#stop').click();
            for (let i = 0; i < 50 && (await (await fetch(`${base}/test-stats`)).json()).active; i++) {
                await page.waitForTimeout(20);
            }
            assert.equal((await (await fetch(`${base}/test-stats`)).json()).active, false);
        }

        // A native-window stream also works through the existing video fallback.
        await page.goto(`${base}/remote?source=ps4`);
        await page.evaluate(() => {
            window.DirectProcessor = window.MediaStreamTrackProcessor;
            window.MediaStreamTrackProcessor = undefined;
            HTMLVideoElement.prototype.requestVideoFrameCallback = window.renderFrameCallback;
        });
        const beforeFallback = (await (await fetch(`${base}/test-stats`)).json()).frames;
        await page.locator('#start').click();
        await page.waitForFunction(() => document.getElementById('source-size').textContent === '960 × 540');
        let fallback;
        for (let i = 0; i < 100; i++) {
            fallback = await (await fetch(`${base}/test-stats`)).json();
            if (fallback.frames >= beforeFallback + 3) break;
            await page.waitForTimeout(50);
        }
        assert(fallback.frames >= beforeFallback + 3);
        // Video rendering may interpolate quadrant boundaries; solid zones stay exact.
        assert.equal(fallback.colors.length, stats.colors.length);
        for (const index of [0, 63, 99, 163, 199]) {
            assert.deepEqual(fallback.colors[index], stats.colors[index]);
        }
        await page.locator('#stop').click();
        for (let i = 0; i < 50 && (await (await fetch(`${base}/test-stats`)).json()).active; i++) {
            await page.waitForTimeout(20);
        }
        await page.goto(`${base}/remote`);
        await page.locator('#source').selectOption('ps4');
        await page.evaluate(() => { window.captureMode = 'unreadable'; });
        await page.locator('#start').click();
        await page.waitForFunction(() => document.getElementById('error').textContent.includes('ne peut pas'));
        assert(await page.locator('#source').isEnabled());
        await page.evaluate(() => { window.captureMode = 'normal'; });
        await page.evaluate(() => {
            window.RealWebSocket = window.WebSocket;
            window.fakeFrameCount = 0;
            window.WebSocket = class {
                static OPEN = 1;
                readyState = 1;
                bufferedAmount = 0;
                constructor() { setTimeout(() => this.onmessage?.({data: '{"type":"ready"}'}), 10); }
                send() { window.fakeFrameCount++; }
                close() { this.readyState = 3; }
            };
        });
        await page.locator('#start').click();
        await page.waitForFunction(() => window.fakeFrameCount === 1);
        await page.waitForTimeout(200);
        assert.equal(await page.evaluate(() => window.fakeFrameCount), 1);
        await page.waitForFunction(() => document.getElementById('error').textContent.includes('serveur ne'), {timeout: 5000});
        await page.evaluate(() => { window.WebSocket = window.RealWebSocket; });
        await page.evaluate(() => { window.captureMode = 'deny'; });
        await page.locator('#start').click();
        await page.waitForFunction(() => document.getElementById('error').textContent.includes('refus'));
        assert(await page.locator('#start').isEnabled());
        await page.evaluate(() => { window.captureMode = 'normal'; });
        await page.locator('#start').click();
        await page.waitForFunction(() => document.getElementById('state').textContent === 'Remote Play actif');
        await page.evaluate(() => window.endTestTrack());
        assert(await page.locator('#start').isEnabled());
        await page.route(`${base}/`, route => route.fulfill({body: '<h1>Plex</h1>', contentType: 'text/html'}));
        await page.locator('#start').click();
        await page.waitForFunction(() => document.getElementById('state').textContent === 'Remote Play actif');
        await page.locator('#back-plex').click();
        await page.waitForURL(`${base}/`);
        for (let i = 0; i < 50 && (await (await fetch(`${base}/test-stats`)).json()).active; i++) {
            await page.waitForTimeout(20);
        }
        assert.equal((await (await fetch(`${base}/test-stats`)).json()).active, false);
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({result: 'PASS', frames: stats.frames, desktop,
            mobile: path.join(os.tmpdir(), 'ambiplex-remote-mobile.png'), checks:
            ['RGBA to real LED engine', 'RGB primary colors', 'capture start/stop/restart',
             'permission denial', 'track ended', 'one outstanding frame', 'ACK timeout',
             'direct frames without rendering callbacks', 'static source stays connected',
             'return to Plex releases capture',
             'PS4 window preference and bookmark', '540p window exact LED colors',
             'manual window-toolbar crop', 'native-window video fallback',
             'source dimensions and surface', 'unreadable window recovery',
             'local Chiaki launch, missing app recovery, no auto capture, cross-origin/GET rejected',
             'server probes survive 17s without frames or heartbeat timers; exact colors on resume',
             'desktop/mobile layout', 'no JS errors']}));
    } finally {
        if (browser) await browser.close();
        server.kill();
        await exited;
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
