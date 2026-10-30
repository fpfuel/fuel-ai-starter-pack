/* UPS Calculate Time and Cost (public page) driver, no UPS account needed.
   Attaches to a plain Chrome over CDP (UPS blocks Playwright-launched browsers), fills the
   form, and prints every service with its rate and delivery estimate as JSON.
     node ups_ctc.mjs --from=60143 --to=96720 --weight=10 [--length=12 --width=24 --height=18]
                      [--qty=1] [--residential] [--date=YYYY-MM-DD] [--cdp=http://127.0.0.1:9222]
                      [--probe]   (dump the page after each step instead of parsing results)
                      [--show]    (leave the rendered quote on screen: raises the Chrome window)
                      [--shot=FILE.png]  (walk in a new tab, save UPS's results page as a picture, close the tab)   */
import { chromium } from 'playwright-core';
const args = Object.fromEntries(process.argv.slice(2).map(a => { const m = a.match(/^--([^=]+)=(.*)$/); return m ? [m[1], m[2]] : [a.replace(/^--/, ''), true]; }));
const need = k => { if (!args[k]) { console.error('missing --' + k); process.exit(2); } return args[k]; };
const FROM = need('from'), TO = need('to'), WEIGHT = need('weight');
const URL = 'https://wwwapps.ups.com/ctc/request?loc=en_US';
const T0 = Date.now(); const lap = (l) => { if (args.timing) console.error(l.padEnd(22), ((Date.now() - T0) / 1000).toFixed(1) + 's'); };

const browser = await chromium.connectOverCDP(args.cdp || `http://127.0.0.1:${process.env.UPS_CHROME_PORT || 9222}`, { timeout: 15000 });
const ctx = browser.contexts()[0];
let page = args.shot ? await ctx.newPage() : (ctx.pages().find(p => p.url().includes('/ctc/')) || await ctx.newPage());
if (args.shot) await page.setViewportSize({ width: 1280, height: 900 }).catch(() => {});
const netlog = [];
if (args.netlog) page.on('response', async r => { const req = r.request(); const t = req.resourceType(); if (!/xhr|fetch|document/.test(t)) return; const ct = (r.headers()['content-type'] || '').split(';')[0]; let body = ''; try { if (/json|html|text/.test(ct)) body = (await r.text()).slice(0, 160).replace(/\s+/g, ' '); } catch {} netlog.push({ at: ((Date.now() - T0) / 1000).toFixed(1), t, m: req.method(), st: r.status(), ct, url: req.url().slice(0, 150), post: (req.postData() || '').slice(req.url().includes('/ctc/results') ? 0 : 0, req.url().includes('/ctc/results') ? 100000 : 500), body: req.url().includes('/ctc/results') ? (await r.text().catch(() => '')) : body }); });
lap('connected'); await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForFunction(() => { const v = e => !!(e && e.offsetParent); return v(document.querySelector('#orig_PostalCode')) || [...document.querySelectorAll('button,a')].some(b => v(b) && b.innerText.trim() === 'Edit'); }, null, { timeout: 20000 }).catch(() => {});
await page.waitForTimeout(300);
// The session remembers the last quote: if step 1 is collapsed, reopen it.
const vis = sel => page.evaluate(sel => { const e = document.querySelector(sel); return !!(e && e.offsetParent); }, sel);
if (!(await vis('#orig_PostalCode'))) { await page.evaluate(() => { const b = [...document.querySelectorAll('button,a')].find(x => x.offsetParent && x.innerText.trim() === 'Edit'); if (b) b.click(); }); await page.waitForSelector('#orig_PostalCode', { state: 'visible', timeout: 10000 }).catch(() => {}); console.log('reopened step 1:', await vis('#orig_PostalCode')); }

const dump = async (label) => {
  const d = await page.evaluate(() => ({
    url: location.href.slice(0, 120),
    inputs: [...document.querySelectorAll('input,select,textarea')].filter(i => i.offsetParent).map(i => ({ t: i.type, n: i.name, id: i.id, lbl: (i.labels && i.labels[0] && i.labels[0].innerText.trim().slice(0, 50)) || '', opts: i.tagName === 'SELECT' ? [...i.options].map(o => o.text.trim()).slice(0, 15) : undefined, v: i.type === 'checkbox' || i.type === 'radio' ? i.checked : (i.value || '').slice(0, 30) })).slice(0, 40),
    buttons: [...document.querySelectorAll('button,input[type=submit],a.btn')].filter(b => b.offsetParent).map(b => (b.innerText || b.value || '').trim().slice(0, 40) + (b.disabled ? ' [disabled]' : '')).filter(Boolean).slice(0, 20),
    errors: [...document.querySelectorAll('[class*=error],[role=alert]')].filter(e => e.offsetParent).map(e => e.innerText.trim().slice(0, 160)).filter(Boolean).slice(0, 8),
    text: document.body.innerText.replace(/\n{2,}/g, '\n').slice(0, 2500),
  }));
  console.log(`\n===== ${label} =====`); console.log(JSON.stringify(d, null, 1));
};

const setSelectByText = (sel, text) => page.evaluate(({ sel, text }) => {
  const s = document.querySelector(sel); if (!s) return 'missing ' + sel;
  const o = [...s.options].find(o => o.text.trim() === text); if (!o) return 'no option ' + text;
  s.value = o.value; s.dispatchEvent(new Event('change', { bubbles: true })); return 'ok';
}, { sel, text });
const setValue = (sel, v) => page.evaluate(({ sel, v }) => { const e = document.querySelector(sel); if (!e) return 'missing ' + sel; e.focus(); e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); e.blur(); return 'ok'; }, { sel, v });
const clickText = (text) => page.evaluate((t) => { const e = [...document.querySelectorAll('button,a,input[type=submit]')].find(x => x.offsetParent && ((x.innerText || x.value || '').trim() === t)); if (!e) return false; e.click(); return true; }, text);

lap('page loaded');
// Step 1: where and when
console.log('origin', await setSelectByText('#orig_Country', 'United States'));
await page.waitForTimeout(800);
console.log('origin zip', await setValue('#orig_PostalCode', FROM));
console.log('dest', await setSelectByText('#dest_Country', 'United States'));
await page.waitForTimeout(800);
console.log('dest zip', await setValue('#dest_PostalCode', TO));
if (args.residential) await page.evaluate(() => { const r = document.querySelector('#rRadio'); if (r) r.click(); });
if (args.date) console.log('date', await setValue('#ctcDatePicker', args.date));
await page.waitForTimeout(500);
console.log('update', await clickText('Update'));
await page.waitForFunction(() => { const v = e => !!(e && e.offsetParent); return v(document.querySelector('label[for=btnSimpleRate_Conventional]')) || v(document.querySelector('#weightValueSec')); }, null, { timeout: 20000 }).catch(() => {});
await page.waitForTimeout(400);
lap('step1 updated');
// Step 2: switch off Simple Rate so weight and dimensions appear
if (!(await vis('#weightValueSec'))) {
  await page.click('label[for=btnSimpleRate_Conventional]', { timeout: 8000 }).catch(e => console.log('label click failed', e.message.slice(0, 80)));
  await page.waitForSelector('#weightValueSec', { state: 'visible', timeout: 10000 }).catch(() => {});
}
console.log('conventional fields visible:', await vis('#weightValueSec'));
if (args.probe === 'step2') {
  const vis = await page.evaluate(() => [...document.querySelectorAll('#packagingTypeList,#weightValueSec,#length,#width,#height,#numberPackagesSelectSec,#weightDropDown,#dimUnitDrop,#weightTypeInput,#packageLength,#packagingTypeListSR')].map(e => ({ id: e.id, vis: !!e.offsetParent, opts: e.tagName === 'SELECT' ? [...e.options].map(o => o.text.trim()).slice(0, 15) : undefined })));
  console.log(JSON.stringify(vis, null, 1)); process.exit(0);
}
lap('conventional on');
// Step 2 fields
const packOpts = await page.evaluate(() => [...document.querySelector('#packagingTypeList').options].map(o => o.text.trim()));
const packChoice = args.packaging || packOpts.find(t => /my packaging|your packaging/i.test(t)) || packOpts[1];
console.log('packaging', packChoice, await setSelectByText('#packagingTypeList', packChoice));
console.log('weight', await setValue('#weightValueSec', String(WEIGHT)));
if (args.length) console.log('dims', await setValue('#length', String(args.length)), await setValue('#width', String(args.width)), await setValue('#height', String(args.height)));
console.log('qty', await setSelectByText('#numberPackagesSelectSec', String(args.qty || 1)));
await page.click('label[for=i_will_pay]', { timeout: 5000 }).catch(() => page.evaluate(() => document.querySelector('#i_will_pay')?.click()));
await page.waitForTimeout(200);
console.log('update', await clickText('Update'));
await page.waitForSelector('table.dataTable', { state: 'visible', timeout: 45000 }).catch(() => {});
await page.waitForFunction(() => /Result estimates calculated by UPS/.test(document.body.innerText), null, { timeout: 45000 }).catch(() => {});
await page.waitForTimeout(500);
if (args.probe === 'results') {
  const r = await page.evaluate(() => ({
    url: location.href.slice(0, 120),
    errors: [...document.querySelectorAll('[class*=error],[role=alert]')].filter(e => e.offsetParent).map(e => e.innerText.trim().slice(0, 200)).filter(Boolean).slice(0, 8),
    tables: [...document.querySelectorAll('table')].filter(t => t.offsetParent).map(t => ({ cls: t.className.toString().slice(0, 50), id: t.id, rows: [...t.querySelectorAll('tr')].slice(0, 12).map(tr => [...tr.children].map(td => td.innerText.trim().replace(/\s+/g, ' ').slice(0, 60))) })).slice(0, 5),
    text: document.body.innerText.split('\n').filter(l => l.trim()).join('\n').slice(2200, 5200),
  }));
  console.log(JSON.stringify(r, null, 1)); process.exit(0);
}
lap('results visible');
// Parse the results table: one row per service, plus the per-service breakdown rows that follow.
const res = await page.evaluate(() => {
  const out = { quotedAt: '', services: [], notes: [] };
  const t = [...document.querySelectorAll('table.dataTable')].find(t => t.offsetParent);
  if (!t) return out;
  let cur = null;
  for (const tr of t.querySelectorAll('tr')) {
    const cells = [...tr.children].map(td => td.innerText.trim().replace(/\s+/g, ' '));
    if (cells.length >= 3 && /USD/.test(cells[2]) && /Latest Pickup|Days In Transit/.test(cells.join(' '))) {
      const name = cells[0].replace(/Latest Pickup Time:.*$/, '').trim();
      const transit = (cells[1].match(/Days In Transit:\s*(\d+)/) || [])[1];
      const delivered = (cells[1].match(/Delivered By:\s*(.*)$/) || [])[1];
      const cost = (cells[2].match(/([\d,]+\.\d\d) USD/) || [])[1];
      const billable = (cells[2].match(/Billable Weight:\s*([\d.]+ lbs\.)/) || [])[1];
      cur = { service: name, daysInTransit: transit ? Number(transit) : null, deliveredBy: delivered || '', totalUSD: cost ? Number(cost.replace(/,/g, '')) : null, billableWeight: billable || '', breakdown: {} };
      out.services.push(cur);
    } else if (cells.length === 2 && /USD/.test(cells[1]) && cells[0]) {
      const label = cells[0].replace(/This will open a new window/, '').trim();
      const svc = out.services.find(s => s.service === label);
      if (svc) cur = svc;
      if (cur) cur.breakdown[svc ? 'base' : label.replace(/:$/, '')] = Number(cells[1].replace(/[^\d.]/g, ''));
    }
  }
  const body = document.body.innerText;
  out.quotedAt = (body.match(/Result estimates calculated by UPS:\s*(.*?)\n/) || [])[1] || '';
  for (const m of body.matchAll(/UPS Ground is not available[^\n]*|The weight exceeds[^\n]*/g)) out.notes.push(m[0]);
  return out;
});
res.request = { from: FROM, to: TO, weightLbs: Number(WEIGHT), dims: args.length ? [args.length, args.width, args.height].map(Number) : null, qty: Number(args.qty || 1), packaging: packChoice, rateBasis: 'retail, paid at a UPS location (no account)' };
lap('parsed');
if (args.show) {
  // Bring the Chrome window to the front with the rendered quote on screen (it is normally parked off-screen).
  try { const cdp = await ctx.newCDPSession(page); const { windowId } = await cdp.send('Browser.getWindowForTarget'); await cdp.send('Browser.setWindowBounds', { windowId, bounds: { left: 80, top: 60, width: 1280, height: 900, windowState: 'normal' } }); await page.bringToFront(); console.error('UPS quote is on screen in the Chrome window'); } catch (e) { console.error('could not raise the window: ' + e.message); }
}
if (args.shot) {
  // The picture is UPS's own page: their header, the shipment as entered, every service, and their timestamp.
  // Cookie notice and chat bubble float over the results, so fixed-position layers are hidden first.
  const clip = await page.evaluate(() => {
    const ot = document.querySelector('#onetrust-consent-sdk'); if (ot) ot.style.setProperty('display', 'none', 'important');
    for (const e of document.querySelectorAll('body *')) {
      if (getComputedStyle(e).position !== 'fixed') continue;
      const r = e.getBoundingClientRect();
      if (r.top > 150 || r.height > 400) e.style.setProperty('display', 'none', 'important');
    }
    const t = [...document.querySelectorAll('table.dataTable')].find(x => x.offsetParent);
    const box = (t && (t.closest('.appLvl') || t.closest('#results'))) || document.querySelector('#results');
    const r = box ? box.getBoundingClientRect() : null;
    return { width: document.documentElement.scrollWidth, bottom: r ? Math.ceil(r.bottom + window.scrollY + 24) : document.documentElement.scrollHeight, found: !!box };
  });
  res.shot = '';
  if (res.services.length) {
    await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(400);
    await page.screenshot({ path: String(args.shot), fullPage: true, clip: { x: 0, y: 0, width: Math.min(clip.width, 1280), height: clip.bottom }, timeout: 30000 });
    res.shot = String(args.shot);
  }
  await page.close().catch(() => {});
}
if (args.netlog) { console.error(JSON.stringify(netlog, null, 1)); }
console.log(JSON.stringify(res, null, 1));
process.exit(0);
