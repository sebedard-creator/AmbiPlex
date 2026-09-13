const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const baseline = execFileSync('git', ['show', '81db0f00bcdf3cc94db47fc597fb028205fa72ab:static/app.js'], { cwd: root });
const config = { leds_top: 64, leds_side: 36, led_depth: 8, led_smoothing: 0 };

async function createPage(browser, script, viewport) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
        window.EventSource = class {
            constructor() { window.testStream = this; }
            close() {}
        };
        const measure = CanvasRenderingContext2D.prototype.measureText;
        window.measureCalls = 0;
        CanvasRenderingContext2D.prototype.measureText = function (...args) {
            window.measureCalls++;
            return measure.apply(this, args);
        };
    });
    await page.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.hostname !== '127.0.0.1') return route.fulfill({ body: '', contentType: 'text/css' });
        if (url.pathname === '/api/config') return route.fulfill({ json: config });
        if (url.pathname === '/static/app.js') return route.fulfill({ body: script, contentType: 'text/javascript' });
        const files = { '/': ['static/index.html', 'text/html'], '/static/style.css': ['static/style.css', 'text/css'] };
        const file = files[url.pathname];
        return file ? route.fulfill({ body: fs.readFileSync(path.join(root, file[0])), contentType: file[1] })
            : route.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://127.0.0.1:5788/');
    await page.waitForFunction(() => document.getElementById('leds_top').value === '64');
    await page.evaluate(() => document.fonts.ready);
    return { page, errors };
}

async function draw(page, x, y, seed, resize) {
    return page.evaluate(({ x, y, seed, resize }) => {
        document.getElementById('leds_top').value = x;
        document.getElementById('leds_side').value = y;
        const canvas = document.getElementById('ledSimulator');
        if (resize) { canvas.width = 520; canvas.height = 300; }
        window.testStream.onmessage({ data: JSON.stringify({ type: 'monitoring', state: 'playing', offset: 1000,
            local_offset: 1000, action: 1, loop_time_ms: 2, dropped_frames: 0, crop_box: [0, 90],
            colors: Array.from({ length: 2 * (x + y) }, (_, i) => [(i*31+seed)%256, (i*59+seed)%256, (i*97+seed)%256]) }) });
        return canvas.toDataURL();
    }, { x, y, seed, resize });
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL });
    let comparisons = 0;
    try {
        for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
            const old = await createPage(browser, baseline, viewport);
            const current = await createPage(browser, fs.readFileSync(path.join(root, 'static/app.js')), viewport);
            for (const [x, y] of [[64, 36], [66, 38], [53, 31], [0, 36], [64, 0]]) {
                for (const seed of [0, 24, 255]) {
                    assert.equal(await draw(current.page, x, y, seed, false), await draw(old.page, x, y, seed, false));
                    comparisons++;
                }
            }
            assert.equal(await draw(current.page, 64, 36, 10, true), await draw(old.page, 64, 36, 10, true));
            comparisons++;
            const before = await current.page.evaluate(() => window.measureCalls);
            await draw(current.page, 64, 36, 20, false);
            assert.equal(await current.page.evaluate(() => window.measureCalls), before, 'cached labels must not be measured again');
            await current.page.evaluate(() => document.fonts.dispatchEvent(new Event('loadingdone')));
            assert.equal(await draw(current.page, 64, 36, 20, false), await draw(old.page, 64, 36, 20, false));
            comparisons++;
            assert.deepEqual(old.errors, []);
            assert.deepEqual(current.errors, []);
            await current.page.screenshot({ path: path.join(os.tmpdir(), `ambiplex-performance-${viewport.width}.png`), fullPage: true });
            await old.page.close();
            await current.page.close();
        }
        console.log(`${comparisons} simulator canvas comparisons: exact equality; no JavaScript errors.`);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
