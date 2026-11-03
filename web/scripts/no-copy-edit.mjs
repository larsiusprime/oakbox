// The live copy editor is in `npm run dev:copy` only (SPEC §6.6): the built app must have none of it.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const assets = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../src/oakbox/web/assets");
// Its names, and its marker character (U+2063) however the minifier writes it.
const signs = ["oakbox-copy-edit", "/__copy/", "oakbox-copy-changed", "fromCharCode(8291)", "\\u2063", String.fromCharCode(0x2063)];
const found = [];
for (const f of fs.readdirSync(assets)) {
  if (!f.endsWith(".js")) continue;
  const text = fs.readFileSync(path.join(assets, f), "utf8");
  for (const s of signs) if (text.includes(s)) found.push(`${f}: ${JSON.stringify(s)}`);
}
if (found.length) {
  console.error(`The build has the live copy editor in it:\n  ${found.join("\n  ")}`);
  process.exit(1);
}
