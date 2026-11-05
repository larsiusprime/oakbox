// How long OAK box's pages take to be usable, in a headless Chromium slowed down like a weak office PC.
//
// Usage: node perf/ui.js <base_url> <project_id> <slowdown> <out.json>
//
// Run by perf/drive.py (--ui) after a run, against the same server, on the finished project. Each page is opened
// from cold, timed until the network is quiet and two frames have been painted, with the time the page spent in long
// tasks (the main thread busy over 50 ms at a stretch: what makes a page feel frozen) and its JavaScript heap. The CPU
// is slowed with Chrome's own throttle (the profile's ui_slowdown); there's no GPU, so maps draw in software, as on
// integrated graphics with acceleration off.

const { chromium } = require("playwright");
const fs = require("fs");

// [label, hash path under the project, a step's button to press there, or null]
const PAGES = [
  ["Data: IDs and the match panel", "fields/sales_ids", null],
  ["Data: Sale date (histogram)", "fields/sale_date", null],
  ["Data: Building size (histogram)", "fields/building_size", null],
  ["Data: Quality (sales by value)", "fields/quality", null],
  ["Data: Location fields (map)", "fields/location", null],
  ["Data: Coordinates (map)", "fields/coordinates", null],
  ["Model groups: build (map)", "groups", /^\d*\s*Build the groups$/],
  ["Check sales: the sales", "sales", /^\d*\s*The sales$/],
  ["Check sales: set aside", "sales", /^\d*\s*Sales set aside$/],
  ["Check my values: summary", "check", /^\d*\s*Summary$/],
  ["Check my values: on the map", "check", /^\d*\s*On the map$/],
  ["Variables: fill blanks", "variables", /^\d*\s*Fill blanks$/],
  ["Variables: variable lists", "variables", /^\d*\s*Variable lists$/],
  ["Models: how they did", "values", /^\d*\s*How they did$/],
  ["Models: model values", "values", /^\d*\s*Model values$/],
  ["Report", "report", null],
];

const OBSERVE = `
window.__long = 0;
try {
  new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__long += e.duration; })
    .observe({ type: 'longtask', buffered: true });
} catch (e) {}
`;

// Ready: the network quiet, none of the app's "…" status lines left (Loading…, Reading the files…, Drawing the
// parcels…), its main panel drawn, and on a page with a map, the map's canvas. Quiet alone isn't enough: with the CPU
// throttled, the page's script can take longer than the quiet spell to start asking for its data.
const BUSY = /^(Loading|Reading|Drawing|Checking the columns|Measuring|Working it out|Writing)\b.*…$/;

async function ready(page, map) {
  const until = Date.now() + 300000;
  while (Date.now() < until) {
    await page.waitForLoadState("networkidle", { timeout: 300000 });
    const busy = await page.getByText(BUSY).count();
    const main = await page.locator(".wiz-main, .panel-body, main, .report").count();
    const drawn = !map || (await page.locator(".map-canvas canvas").count());
    if (!busy && main && drawn) return;
    await page.waitForTimeout(250);
  }
  throw new Error("still loading after 300 s");
}

(async () => {
  const [base, pid, slowdown, out] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ["--disable-gpu"] });
  const rows = [];
  for (const [label, path, press] of PAGES) {
    const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
    const page = await ctx.newPage();
    await page.addInitScript(OBSERVE);
    const cdp = await ctx.newCDPSession(page);
    if (Number(slowdown) > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: Number(slowdown) });
    const row = { page: label, error: null };
    try {
      const t = Date.now();
      await page.goto(`${base}/#/projects/${pid}/${path}`, { waitUntil: "load", timeout: 180000 });
      const map = label.includes("(map)") || label.includes("on the map");
      await ready(page, map && !press);
      if (press) {
        // The step in the tab's list, pressed as a user would (its timing includes the tab's overview first).
        const btn = page.getByRole("button", { name: press }).first();
        try {
          await btn.waitFor({ timeout: 60000 });
          await btn.click({ timeout: 60000 });
          await ready(page, map);
        } catch (e) {
          row.error = `no '${press}' step`;
        }
      }
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      row.ready_s = Math.round((Date.now() - t) / 10) / 100;
      row.long_tasks_s = Math.round((await page.evaluate(() => window.__long || 0)) / 10) / 100;
      const heap = await page.evaluate(() => (performance.memory ? performance.memory.usedJSHeapSize : null));
      row.js_heap_mb = heap ? Math.round(heap / 2 ** 20 * 10) / 10 : null;
      if (process.env.UI_SHOTS) {
        fs.mkdirSync(process.env.UI_SHOTS, { recursive: true });
        await page.screenshot({ path: `${process.env.UI_SHOTS}/${rows.length + 1}.png` });
      }
    } catch (e) {
      row.error = `${e.name}: ${String(e.message).slice(0, 200)}`;
    }
    console.log(`ui ${label}: ${JSON.stringify(row)}`);
    rows.push(row);
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(out, JSON.stringify(rows, null, 1));
})();
