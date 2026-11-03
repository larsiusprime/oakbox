// The live copy editor's half on the dev server (SPEC §6.6; vite.config.ts adds it in `npm run dev:copy` only).
//   POST /__copy/save {key, source, was}  writes one message into src/copy/en.json
//   GET  /__copy/uses?key=…               where the code names it (by its last part)
// The file is read again before each save, so what was changed in it meanwhile is kept; a message changed in the
// file since the editor opened it isn't overwritten. A message must stay valid ICU with the same arguments (the
// same types: copy.gen.ts, regenerated after). Vite sees en.json change, and the page refills its copy (catalog.ts).
import fs from "node:fs";
import path from "node:path";
import { DIR, messageType, write as writeTypes } from "./copy-types.mjs";

const FILE = path.join(DIR, "en.json");
const SRC = path.join(DIR, "..");

function body(req) {
  return new Promise((resolve, reject) => {
    let s = "";
    req.on("data", (c) => (s += c));
    req.on("end", () => resolve(s));
    req.on("error", reject);
  });
}

function reply(res, status, value) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json");
  res.end(JSON.stringify(value));
}

function save({ key, source, was }) {
  if (typeof key !== "string" || typeof source !== "string") return [400, { error: "Needs a key and a source." }];
  if (/[\r\n]/.test(source)) return [400, { error: "A message is one line." }];
  const catalog = JSON.parse(fs.readFileSync(FILE, "utf8"));
  const keys = key.split(".");
  const last = keys.pop();
  const parent = keys.reduce((o, k) => (o == null ? o : o[k]), catalog);
  const current = parent?.[last];
  if (typeof current !== "string") return [404, { error: `No message ${key} in en.json.` }];
  if (typeof was === "string" && was !== current)
    return [409, { error: "It was changed in en.json since you opened it: open it again to edit the new words." }];
  let before;
  let after;
  try {
    before = messageType(current, key);
    after = messageType(source, key);
  } catch (e) {
    return [400, { error: e.message }];
  }
  if (before !== after) return [400, { error: `Its arguments changed: they were ${before}, now ${after}.` }];
  if (current === source) return [200, { ok: true, unchanged: true }];
  parent[last] = source;
  fs.writeFileSync(FILE, `${JSON.stringify(catalog, null, 2)}\n`);
  writeTypes();
  return [200, { ok: true }];
}

// Where the code names a message: the longest end of its key that the code has (`tabs.scrollLeft`, else
// `scrollLeft`), since code often reaches it through a shorter name (`const s = t.sales; s.review…`).
function uses(key) {
  const parts = key.split(".").filter((p) => !/^\d+$/.test(p));
  const files = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (/\.tsx?$/.test(e.name) && !e.name.endsWith(".gen.ts"))
        files.push([path.relative(SRC, p), fs.readFileSync(p, "utf8").split("\n")]);
    }
  };
  walk(SRC);
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  for (let n = Math.min(parts.length, 3); n >= 1; n--) {
    const name = parts.slice(-n).join(".");
    const re = new RegExp(`[.]${esc(name)}\\b`);
    const where = [];
    for (const [f, lines] of files) lines.forEach((line, i) => re.test(line) && where.push(`${f}:${i + 1}`));
    if (where.length || n === 1) return { n: where.length, where: where.slice(0, 40), name };
  }
}

export function copyEdit() {
  return {
    name: "oakbox-copy-edit",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__copy/save", async (req, res) => {
        if (req.method !== "POST") return reply(res, 405, { error: "POST only" });
        try {
          const [status, value] = save(JSON.parse(await body(req)));
          reply(res, status, value);
        } catch (e) {
          reply(res, 500, { error: String(e?.message ?? e) });
        }
      });
      server.middlewares.use("/__copy/uses", (req, res) => {
        const key = new URL(req.url ?? "", "http://x").searchParams.get("key") ?? "";
        reply(res, 200, uses(key));
      });
    },
  };
}
