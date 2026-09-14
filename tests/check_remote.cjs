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
            HTMLVideoElement.prototype.requestVideoFrameCallback = () => {
                throw Error('Rendering callbacks must not be used by the direct capture path');
            };
            navigator.mediaDevices.getDisplayMedia = async () => {
                if (window.captureMode === 'deny') throw new DOMException('Denied', 'NotAllowedError');
                const source = document.createElement('canvas');
                source.width = 1280;
                source.height = 720;
                const ctx = source.getContext('2d');
                let tick = 0;
                const draw = () => {
                    ctx.fillStyle = '#e02020'; ctx.fillRect(0, 0, 640, 360);
                    ctx.fillStyle = '#20d040'; ctx.fillRect(640, 0, 640, 360);
                    ctx.fillStyle = '#2040e0'; ctx.fillRect(0, 360, 640, 360);
                    ctx.fillStyle = '#e0c020'; ctx.fillRect(640, 360, 640, 360);
                    ctx.fillStyle = tick++ % 2 ? '#fff' : '#888'; ctx.fillRect(600, 300, 80, 80);
                };
                draw();
                const timer = setInterval(draw, 16);
                window.freezeTestInput = () => clearInterval(timer);
                const stream = source.captureStream(60);
                const track = stream.getVideoTracks()[0];
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
             'desktop/mobile layout', 'no JS errors']}));
    } finally {
        if (browser) await browser.close();
        server.kill();
        await exited;
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
