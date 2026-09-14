const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const config = {
    plex_url: 'http://127.0.0.1:32400', plex_token: 'synthetic-test-token',
    master_client: 'Sony Bravia', headless: false, sync_offset_frames: 3,
    presets: {'Sony Bravia / 4K HDR / Direct Play': 3}, current_preset: 'Sony Bravia / 4K HDR / Direct Play',
    wled_ip: '192.0.2.1', leds_top: 64, leds_side: 36, led_depth: 8,
    led_smoothing: 0, led_brightness_top: 80, led_brightness_right: 80,
    led_brightness_bottom: 80, led_brightness_left: 80, led_refresh_rate: 30,
    led_refresh_native: false, led_corner_gap: 2, led_start_pos: 'bottom_left',
    led_direction: 'counter_clockwise', offset_top: 1, offset_right: -2,
    offset_bottom: 3, offset_left: -4, disable_autocrop: true,
};

(async () => {
    const browser = await chromium.launch({headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome'});
    const screenshots = [];
    try {
        for (const width of [1440, 768, 390, 320]) {
            const page = await browser.newPage({viewport: {width, height: 900}});
            const errors = [];
            const submissions = [];
            let encoderPayload;
            page.on('pageerror', error => errors.push(error.message));
            await page.addInitScript(() => {
                window.EventSource = class {
                    constructor() { window.mockEvents = this; }
                    close() {}
                };
            });
            await page.route('**/*', route => {
                const request = route.request();
                const url = new URL(request.url());
                if (url.pathname === '/api/config') {
                    if (request.method() === 'POST') {
                        submissions.push(request.postDataJSON());
                        return route.fulfill({json: {status: 'success'}});
                    }
                    return route.fulfill({json: config});
                }
                if (url.pathname === '/api/encoder/browse') return route.fulfill({json: {path: 'C:/Videos/Test Movie.mkv', exists: false}});
                if (url.pathname === '/api/encoder/start') {
                    encoderPayload = request.postDataJSON();
                    return route.fulfill({json: {status: 'success'}});
                }
                const pages = {'/': 'index.html', '/remote': 'remote.html', '/encoder': 'encoder.html'};
                const name = pages[url.pathname] || path.basename(url.pathname);
                const allowed = ['index.html', 'remote.html', 'encoder.html', 'style.css', 'remote.css', 'app.js', 'remote.js'];
                if (!allowed.includes(name)) return route.fulfill({status: 404, body: ''});
                return route.fulfill({body: fs.readFileSync(path.join(root, 'static', name)),
                    contentType: name.endsWith('.css') ? 'text/css' : name.endsWith('.js') ? 'text/javascript' : 'text/html'});
            });
            for (const [url, name] of [['/', 'plex'], ['/encoder', 'encoder'], ['/remote', 'remote']]) {
                await page.goto(`http://127.0.0.1:5788${url}`);
                if (name === 'plex') {
                    await page.waitForFunction(() => document.getElementById('leds_top').value === '64');
                    await page.evaluate(() => window.mockEvents.onmessage({data: JSON.stringify({
                        type: 'monitoring', state: 'playing (remote)', offset: 123456,
                        local_offset: 123456, action: 'REMOTE', loop_time_ms: 1, dropped_frames: 0,
                        crop_box: [0, 90], colors: Array.from({length: 200}, (_, i) => [i % 255, 100, 220]),
                    })}));
                    await page.locator('#btn_save').click();
                    await page.waitForFunction(() => !document.getElementById('saveMsg').classList.contains('hidden'));
                    assert.deepEqual(submissions.at(-1), config);
                    await page.locator('#led_brightness_top').evaluate(el => {
                        el.dispatchEvent(new MouseEvent('mousedown')); el.value = '70'; el.dispatchEvent(new Event('input', {bubbles: true}));
                    });
                    for (const side of ['top', 'right', 'bottom', 'left']) assert.equal(await page.locator(`#led_brightness_${side}`).inputValue(), '70');
                    await page.locator('#brightness_lock_btn').uncheck();
                    await page.locator('#led_brightness_left').evaluate(el => {
                        el.dispatchEvent(new MouseEvent('mousedown')); el.value = '50'; el.dispatchEvent(new Event('input', {bubbles: true}));
                    });
                    assert.equal(await page.locator('#led_brightness_top').inputValue(), '70');
                    await page.locator('#btn_calibrate').click();
                    await page.waitForFunction(() => document.getElementById('btn_calibrate').textContent.includes('Appliqu'));
                    assert.equal(submissions.at(-1).led_brightness_left, 50);
                    assert.equal(submissions.at(-1).plex_token, config.plex_token);
                    assert(await page.locator('#brightness_lock_btn').isVisible());
                    assert.equal(await page.locator('#brightness_lock_btn').isChecked(), false);
                } else if (name === 'encoder') {
                    await page.waitForFunction(() => document.getElementById('leds_x').value === '64');
                    assert(await page.locator('#btn_encode').isDisabled());
                    await page.locator('#btn_browse').click();
                    await page.waitForFunction(() => !document.getElementById('btn_encode').disabled);
                    await page.locator('#btn_encode').click();
                    await page.waitForFunction(() => !!window.mockEvents);
                    assert.deepEqual(encoderPayload, {video_path: 'C:/Videos/Test Movie.mkv', leds_x: 64, leds_y: 36, depth: 8, threads: 0});
                    await page.evaluate(() => {
                        window.mockEvents.onmessage({data: JSON.stringify({type: 'log', message: 'Encodage : 100 %\n'})});
                        window.mockEvents.onmessage({data: JSON.stringify({type: 'done', message: 'Termine'})});
                    });
                    assert(await page.locator('#btn_browse').isEnabled());
                } else {
                    assert.equal(await page.locator('#back-plex').getAttribute('href'), '/');
                }
                const overflow = await page.evaluate(() => ({
                    page: document.documentElement.scrollWidth > innerWidth,
                    controls: [...document.querySelectorAll('input,select,button,a.btn')].filter(el => {
                        const rect = el.getBoundingClientRect();
                        const editableText = el.tagName === 'INPUT' && ['text', 'password'].includes(el.type);
                        return rect.width && (rect.left < -1 || rect.right > innerWidth + 1
                            || (!editableText && el.scrollWidth > el.clientWidth + 2));
                    }).map(el => el.id || el.textContent),
                }));
                assert.deepEqual(overflow, {page: false, controls: []}, `${name} at ${width}`);
                const background = await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor);
                assert.equal(background, 'rgb(17, 19, 21)');
                if (width === 1440 || width === 390) {
                    const file = path.join(os.tmpdir(), `ambiplex-ui-${name}-${width}.png`);
                    await page.screenshot({path: file, fullPage: true});
                    screenshots.push(file);
                }
            }
            assert.deepEqual(errors, []);
            await page.close();
        }
        console.log(JSON.stringify({result: 'PASS', layouts: 12, screenshots,
            checks: ['Plex configuration payload', 'LED calibration payload', 'linked/unlinked brightness',
                'encoder browse/start/completion', 'navigation', 'shared palette', 'no control overflow', 'no JS errors']}));
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
