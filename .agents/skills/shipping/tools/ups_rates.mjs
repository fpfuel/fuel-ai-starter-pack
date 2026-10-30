/* UPS retail rates in about 1.5 s: replays the Calculate Time and Cost rate POST from a warm tab.
   Needs a HEADED plain Chrome with --remote-debugging-port (UPS blocks Playwright-launched and
   headless browsers). The tab keeps the session; the POST body is the captured form template with
   the shipment fields substituted. No UPS account needed; prices are retail, paid at a UPS location.
     node ups_rates.mjs --from=60143 --to=96720 --weight=10 [--length=12 --width=24 --height=18]
                        [--qty=1] [--residential] [--cdp=http://127.0.0.1:9222] [--pretty]
   Several lanes in one process (one Chrome connection, requests in parallel):
     node ups_rates.mjs --lanes='[{"id":"a","from":"02184","to":"96813","weight":4,"length":9,"width":6,"height":5}, ...]'
   prints {"lanes":[{id, ...result}], latencySec}.                                                   */
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).map(a => { const m = a.match(/^--([^=]+)=(.*)$/); return m ? [m[1], m[2]] : [a.replace(/^--/, ''), true]; }));
const T0 = Date.now();
const here = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE = fs.readFileSync(path.join(here, 'ups_ctc_template.txt'), 'utf8');

let lanes;
if (args.lanes) {
  lanes = JSON.parse(fs.existsSync(String(args.lanes)) ? fs.readFileSync(String(args.lanes), 'utf8') : args.lanes);
} else {
  const need = k => { if (!args[k]) { console.error('missing --' + k); process.exit(2); } return args[k]; };
  lanes = [{ id: 'lane', from: need('from'), to: need('to'), weight: need('weight'), length: args.length, width: args.width, height: args.height, qty: args.qty, residential: !!args.residential }];
}

function bodyFor(l) {
  const p = new URLSearchParams(TEMPLATE);
  const set = (k, v) => p.set(k, String(v));
  const today = new Date();
  const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const us = `${String(today.getMonth() + 1).padStart(2, '0')}/${String(today.getDate()).padStart(2, '0')}/${today.getFullYear()}`;
  set('origPostalCode', l.from); set('origPostal', l.from); set('destPostalCode', l.to); set('destPostal', l.to);
  set('weight1', l.weight); set('weight', l.weight);
  if (l.length) { set('length1', l.length); set('width1', l.width); set('height1', l.height); } else { set('length1', ''); set('width1', ''); set('height1', ''); }
  set('packages', l.qty || 1); set('packagesMod1', l.qty || 1); set('noofpackages', l.qty || 1);
  set('shipDate', iso); set('pickerDate', us);
  if (l.residential) { set('destRes', '01'); set('ratingDestTypeRes', '01'); }
  return p.toString();
}

const browser = await chromium.connectOverCDP(args.cdp || 'http://127.0.0.1:9222', { timeout: 15000 });
const ctx = browser.contexts()[0];
let page = ctx.pages().find(p => p.url().includes('wwwapps.ups.com/ctc/'));
if (!page) { page = await ctx.newPage(); await page.goto('https://wwwapps.ups.com/ctc/request?loc=en_US', { waitUntil: 'domcontentloaded', timeout: 60000 }); await page.waitForTimeout(2500); }

// Runs in the page: one fetch per lane, all in flight at once, parsed in the page.
const results = await page.evaluate(async (bodies) => {
  const one = async (body) => {
    const resp = await fetch('/ctc/results', { method: 'POST', body, credentials: 'include', headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest' } });
    const html = await resp.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const out = { status: resp.status, quotedAt: '', services: [], notes: [], unavailable: /System Temporarily Unavailable/.test(html) };
    const t = doc.querySelector('table.dataTable');
    if (!t) return out;
    let cur = null;
    for (const tr of t.querySelectorAll('tr')) {
      const cells = [...tr.children].map(td => td.textContent.trim().replace(/\s+/g, ' '));
      if (cells.length >= 3 && /USD/.test(cells[2]) && /Latest Pickup|Days In Transit/.test(cells.join(' '))) {
        const name = cells[0].replace(/Latest Pickup Time:.*$/, '').trim();
        const transit = (cells[1].match(/Days In Transit:\s*(\d+)/) || [])[1];
        const delivered = (cells[1].match(/Delivered By:\s*(.*)$/) || [])[1];
        const cost = (cells[2].match(/([\d,]+\.\d\d) USD/) || [])[1];
        const billable = (cells[2].match(/Billable Weight:\s*([\d.]+ lbs\.)/) || [])[1];
        cur = { service: name, daysInTransit: transit ? Number(transit) : null, deliveredBy: (delivered || '').replace(/View Details.*$/, '').trim(), totalUSD: cost ? Number(cost.replace(/,/g, '')) : null, billableWeight: billable || '', breakdown: {} };
        out.services.push(cur);
      } else if (cells.length === 2 && /USD/.test(cells[1]) && cells[0]) {
        const label = cells[0].replace(/This will open a new window/, '').replace(/:$/, '').trim();
        const svc = out.services.find(s => s.service === label);
        if (svc) cur = svc;
        if (cur) cur.breakdown[svc ? 'base' : label] = Number(cells[1].replace(/[^\d.]/g, ''));
      }
    }
    const text = doc.body.textContent;
    out.quotedAt = (text.match(/Result estimates calculated by UPS:\s*([^\n]*?)\s{2,}/) || [])[1] || '';
    for (const m of text.matchAll(/UPS Ground is not available[^.]*\.|The weight exceeds[^.]*\./g)) out.notes.push(m[0].trim());
    return out;
  };
  return Promise.all(bodies.map(b => one(b).catch(e => ({ status: 0, services: [], notes: [String(e)], unavailable: false }))));
}, lanes.map(bodyFor));

const out = lanes.map((l, i) => ({ id: l.id || String(i), ...results[i],
  request: { from: l.from, to: l.to, weightLbs: Number(l.weight), dims: l.length ? [l.length, l.width, l.height].map(Number) : null, qty: Number(l.qty || 1), residential: !!l.residential, packaging: 'My Packaging', rateBasis: 'retail, paid at a UPS location (no account)' } }));
const latencySec = Number(((Date.now() - T0) / 1000).toFixed(2));

if (args.lanes) {
  console.log(JSON.stringify({ lanes: out, latencySec }, null, 1));
  process.exit(out.every(r => r.services.length) ? 0 : 1);
}
const res = { ...out[0], latencySec }; delete res.id;
if (args.pretty) {
  console.log(`UPS ${res.request.from} -> ${res.request.to}, ${res.request.weightLbs} lb${res.request.dims ? ` ${res.request.dims.join('x')} in` : ''}, ${res.quotedAt || 'quoted now'}`);
  for (const s of res.services) console.log(`  ${s.service.padEnd(22)} $${s.totalUSD.toFixed(2).padStart(8)}  ${s.daysInTransit} days  ${s.deliveredBy}`);
  for (const n of res.notes) console.log('  note: ' + n);
  console.log(`  (${res.latencySec}s)`);
} else console.log(JSON.stringify(res, null, 1));
if (!res.services.length) { console.error(res.unavailable ? 'UPS returned System Temporarily Unavailable: the tab needs a real page load first' : 'no services parsed'); process.exit(1); }
process.exit(0);
