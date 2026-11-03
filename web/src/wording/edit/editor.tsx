/** The live wording editor (SPEC §6.6), `npm run dev:wording` only: Alt+click any text to edit the message it came from;
 * the ✎ Wording button lists the messages on the screen (and finds any other). Saving writes en.json through the dev
 * server (scripts/wording-edit-plugin.mjs); the catalog then refills `t` (catalog.ts) and the words change on the screen
 * here, with nothing reloaded. */
import { parse, TYPE } from "@formatjs/icu-messageformat-parser";
import { IntlMessageFormat } from "intl-messageformat";
import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { sources, t } from "../catalog";
import { allSpans, around, hasMarks, SENTINEL, type Span, shown, spans, strip } from "../marks";

const HOST = "wording-edit";
const ATTRS = ["title", "aria-label", "placeholder", "alt", "aria-description"];
const locale = new Intl.NumberFormat().resolvedOptions().locale;

// ── What's on the screen ──────────────────────────────────────────────────────────────────────────────────────────

const inHost = (n: Node | null) =>
  !!n && (n instanceof Element ? n : n.parentElement)?.closest(`#${HOST}`) != null;

function textNodes(): Text[] {
  const out: Text[] = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode())
    if (hasMarks(n.nodeValue ?? "") && !inHost(n)) out.push(n as Text);
  return out;
}

function markedAttrs(): [Element, string][] {
  const out: [Element, string][] = [];
  const sel = ATTRS.map((a) => `[${a}]`).join(",");
  for (const el of Array.from(document.body.querySelectorAll(sel)))
    if (!inHost(el)) for (const a of ATTRS) if (hasMarks(el.getAttribute(a) ?? "")) out.push([el, a]);
  return out;
}

const title = () => (window as { __wordingTitle?: string }).__wordingTitle ?? "";

/** The marker numbers on the screen now, in page order, once each. */
function onScreen(): number[] {
  const seen = new Set<number>();
  const add = (s: string) => {
    for (const sp of allSpans(s)) seen.add(sp.n);
  };
  add(title());
  for (const n of textNodes()) add(n.nodeValue ?? "");
  for (const [el, a] of markedAttrs()) add(el.getAttribute(a) ?? "");
  return [...seen];
}

// ── Putting new words on the screen ───────────────────────────────────────────────────────────────────────────────

const at = (key: string): unknown =>
  key.split(".").reduce<unknown>((o, k) => (o == null ? o : (o as Record<string, unknown>)[k]), t);

/** A message as it reads now, with the arguments it was shown with (and its markers). */
function now(n: number): string | null {
  const s = shown[n];
  if (!s) return null;
  const v = at(s.key);
  if (typeof v === "function") return (v as (a: unknown) => string)(s.args ?? {});
  return typeof v === "string" ? v : null;
}

/** The string with each message in `redo` as it reads now (the ones around it kept as they are). */
function rewrite(s: string, redo: Set<number>): string {
  const out = (level: Span[], from: number, to: number): string => {
    let r = "";
    let i = from;
    for (const sp of level) {
      r += s.slice(i, sp.start);
      if (sp.end < 0) return r + s.slice(sp.start, to); // cut off: left as it is
      const fresh = redo.has(sp.n) ? now(sp.n) : null;
      r +=
        fresh ??
        s.slice(sp.start, sp.textStart) +
          out(sp.inner, sp.textStart, sp.textEnd) +
          s.slice(sp.textEnd, sp.end);
      i = sp.end;
    }
    return r + s.slice(i, to);
  };
  return out(spans(s), 0, s.length);
}

function refresh(keys: string[]) {
  const redo = new Set<number>();
  const changed = new Set(keys);
  shown.forEach((s, n) => {
    if (changed.has(s.key)) redo.add(n);
  });
  if (!redo.size) return;
  for (const node of textNodes()) {
    const v = node.nodeValue ?? "";
    const w = rewrite(v, redo);
    if (w !== v) node.nodeValue = w;
  }
  for (const [el, a] of markedAttrs()) {
    const v = el.getAttribute(a) ?? "";
    const w = rewrite(v, redo);
    if (w !== v) el.setAttribute(a, w);
  }
  const was = title();
  if (was) {
    const w = rewrite(was, redo);
    if (w !== was) document.title = w;
  }
}

// ── Finding what was clicked ──────────────────────────────────────────────────────────────────────────────────────

function caretAt(x: number, y: number): { node: Node; offset: number } | null {
  const d = document as Document & {
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
  };
  const p = d.caretPositionFromPoint?.(x, y);
  if (p) return { node: p.offsetNode, offset: p.offset };
  const r = document.caretRangeFromPoint?.(x, y);
  return r ? { node: r.startContainer, offset: r.startOffset } : null;
}

/** The messages at a click, innermost first (then the ones it's part of). Text without markers isn't wording (the
 * user's data, OpenAVMKit's own words): nothing. Off text (an icon, a field), the element's own labels. */
function clicked(e: MouseEvent): number[] {
  const out: number[] = [];
  const add = (n: number) => !out.includes(n) && out.push(n);
  const c = caretAt(e.clientX, e.clientY);
  const target = e.target instanceof Element ? e.target : null;
  if (c && c.node.nodeType === Node.TEXT_NODE && c.node.parentElement && target?.contains(c.node)) {
    const s = c.node.nodeValue ?? "";
    // A click past a letter's middle lands on the next offset: look a character either side too.
    for (const off of [c.offset, c.offset - 1]) for (const sp of around(s, Math.max(0, off))) add(sp.n);
    return out;
  }
  let el = target;
  for (let depth = 0; el && depth < 3 && out.length === 0; depth++, el = el.parentElement)
    for (const a of ATTRS) for (const sp of allSpans(el.getAttribute(a) ?? "")) add(sp.n);
  if (!out.length && target) for (const sp of allSpans(target.textContent ?? "")) add(sp.n);
  return out;
}

// ── Showing a message's source for editing ───────────────────────────────────────────────────────────────────────

/** Each plural or select case on a line of its own; `flat` puts it back (the wording has no line breaks of its own). */
function pretty(src: string): string {
  let ast: ReturnType<typeof parse>;
  try {
    ast = parse(src, { ignoreTag: true, captureLocation: true });
  } catch {
    return src;
  }
  const breaks: { at: number; depth: number }[] = [];
  const walk = (els: ReturnType<typeof parse>, depth: number) => {
    for (const e of els) {
      if (e.type === TYPE.plural || e.type === TYPE.select) {
        for (const [k, o] of Object.entries(e.options)) {
          const open = o.location?.start.offset ?? -1;
          const sel = src.lastIndexOf(k, open);
          if (sel > 0 && src[sel - 1] === " ") breaks.push({ at: sel - 1, depth: depth + 1 });
          walk(o.value, depth + 1);
        }
      }
    }
  };
  walk(ast, 0);
  let out = src;
  for (const b of breaks.sort((x, y) => y.at - x.at))
    out = `${out.slice(0, b.at)}\n${"  ".repeat(b.depth)}${out.slice(b.at + 1)}`;
  return out;
}
const flat = (s: string) => s.replace(/\n */g, " ");
// ICU doubles an apostrophe (''); the editor shows one, and doubles each again on save. A quoted brace or # ('{')
// stays as it is.
const unquote = (s: string) => s.replace(/''|'([{}#])'/g, (m, q) => (q ? m : "'"));
const requote = (s: string) => s.replace(/'([{}#])'|'/g, (m, q) => (q ? m : "''"));

function argNames(src: string): string[] | null {
  try {
    const names = new Set<string>();
    const walk = (els: ReturnType<typeof parse>) => {
      for (const e of els) {
        if (e.type !== TYPE.literal && "value" in e && typeof e.value === "string") names.add(e.value);
        if (e.type === TYPE.plural || e.type === TYPE.select)
          for (const o of Object.values(e.options)) walk(o.value);
      }
    };
    walk(parse(src, { ignoreTag: true }));
    return [...names].sort();
  } catch {
    return null;
  }
}

const shownArgs = (args: Record<string, unknown> | null) =>
  args
    ? Object.fromEntries(Object.entries(args).map(([k, v]) => [k, typeof v === "string" ? strip(v) : v]))
    : null;

function render(src: string, args: Record<string, unknown> | null): { text?: string; error?: string } {
  try {
    if (!args && argNames(src)?.length) {
      parse(src, { ignoreTag: true });
      return {};
    }
    const f = new IntlMessageFormat(src, locale, undefined, { ignoreTag: true });
    return { text: String(f.format(shownArgs(args) ?? {})) };
  } catch (e) {
    return { error: (e as Error).message };
  }
}

type Open = { key: string; args: Record<string, unknown> | null; around: number[]; x: number; y: number };

function EditBox({ open, close, pick }: { open: Open; close: () => void; pick: (n: number) => void }) {
  const original = sources.get(open.key) ?? "";
  const [text, setText] = useState(() => unquote(pretty(original)));
  const [state, setState] = useState<{ saving?: boolean; error?: string; saved?: boolean }>({});
  const [uses, setUses] = useState<{ n: number; where: string[] } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const src = requote(flat(text));
  const names = useMemo(() => argNames(original), [original]);
  const now = argNames(src);
  const sameArgs = now !== null && names !== null && now.join() === names.join();
  const preview = render(src, open.args);

  useEffect(() => {
    void fetch(`/__wording/uses?key=${encodeURIComponent(open.key)}`)
      .then((r) => r.json())
      .then(setUses)
      .catch(() => setUses(null));
  }, [open.key]);

  // On the screen, kept inside the window.
  const [pos, setPos] = useState({ left: open.x, top: open.y });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    setPos({
      left: Math.max(8, Math.min(open.x, window.innerWidth - w - 8)),
      top: Math.max(8, Math.min(open.y + 12, window.innerHeight - h - 8)),
    });
  }, [open.x, open.y]);

  const save = async () => {
    if (!sameArgs || preview.error) return;
    if (src === original) return close();
    setState({ saving: true });
    const r = await fetch("/__wording/save", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ key: open.key, source: src, was: original }),
    });
    const body = (await r.json().catch(() => ({}))) as { error?: string };
    if (!r.ok) setState({ error: body.error ?? `Not saved (${r.status})` });
    else {
      setState({ saved: true });
      setTimeout(close, 400);
    }
  };

  return (
    <div
      className="ce-box"
      ref={box}
      style={pos}
      role="dialog"
      aria-label="Edit wording"
      onKeyDown={(e) => {
        if (e.key === "Escape") close();
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void save();
      }}
    >
      <div className="ce-key">
        <code>{open.key}</code>
        {uses && (
          <span className="ce-uses" title={uses.where.join("\n")}>
            named in {uses.n} {uses.n === 1 ? "place" : "places"}
          </span>
        )}
      </div>
      {open.around.length > 0 && (
        <div className="ce-around">
          Also here:{" "}
          {open.around.map((n) => (
            <button type="button" key={n} onClick={() => pick(n)}>
              {shown[n]?.key}
            </button>
          ))}
        </div>
      )}
      <textarea
        // biome-ignore lint/a11y/noAutofocus: a developer's editor, opened by Alt+click to type into at once.
        autoFocus
        spellCheck
        value={text}
        rows={Math.min(14, Math.max(3, text.split("\n").length + Math.ceil(text.length / 70)))}
        onChange={(e) => setText(e.target.value)}
      />
      {open.args ? (
        <div className="ce-args">
          Shown with{" "}
          {Object.entries(shownArgs(open.args) ?? {}).map(([k, v]) => (
            <span key={k}>
              <code>{k}</code> = {JSON.stringify(v)}
            </span>
          ))}
        </div>
      ) : names?.length ? (
        <div className="ce-args">Not on the screen: no values to show it with.</div>
      ) : null}
      {preview.error ? (
        <div className="ce-bad">Not a valid message: {preview.error}</div>
      ) : !sameArgs ? (
        <div className="ce-bad">
          Keep its arguments, each once or more: {names?.map((n) => `{${n}}`).join(" ")}
        </div>
      ) : (
        preview.text !== undefined && <div className="ce-preview">{preview.text}</div>
      )}
      {state.error && <div className="ce-bad">{state.error}</div>}
      <div className="ce-foot">
        <span>Ctrl+Enter saves · Esc closes</span>
        <button type="button" onClick={close}>
          Cancel
        </button>
        <button
          type="button"
          disabled={!sameArgs || !!preview.error || state.saving}
          onClick={() => void save()}
        >
          {state.saved ? "Saved" : state.saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}

function Panel({ edit }: { edit: (key: string, n: number | null) => void }) {
  const [q, setQ] = useState("");
  const [list, setList] = useState<number[]>(onScreen);
  useEffect(() => {
    const id = setInterval(() => setList(onScreen()), 1500);
    return () => clearInterval(id);
  }, []);
  const query = q.trim().toLowerCase();
  const found = query
    ? [...sources]
        .filter(([k, v]) => k.toLowerCase().includes(query) || v.toLowerCase().includes(query))
        .slice(0, 200)
    : null;
  const seenKeys = new Set<string>();
  const here = list.filter((n) => {
    const k = shown[n]?.key;
    if (!k || seenKeys.has(k)) return false;
    seenKeys.add(k);
    return true;
  });
  return (
    <div className="ce-panel">
      <input
        placeholder="Find any message (its words or key)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="ce-list">
        {found
          ? found.map(([k, v]) => (
              <button type="button" key={k} onClick={() => edit(k, null)}>
                <code>{k}</code>
                <span>{unquote(v)}</span>
              </button>
            ))
          : here.map((n) => {
              const k = shown[n]?.key ?? "";
              return (
                <button type="button" key={k} onClick={() => edit(k, n)}>
                  <code>{k}</code>
                  <span>{strip(now(n) ?? "")}</span>
                </button>
              );
            })}
        {!found && !here.length && <p>No messages on the screen.</p>}
      </div>
      <p className="ce-hint">
        {found ? `${found.length} found` : `${here.length} on the screen`} · Alt+click any text to edit it
      </p>
    </div>
  );
}

function Editor() {
  const [open, setOpen] = useState<Open | null>(null);
  const [panel, setPanel] = useState(false);
  const [note, setNote] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const stop = (e: MouseEvent | PointerEvent) => {
      if (!e.altKey || inHost(e.target as Node)) return;
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    const onClick = (e: MouseEvent) => {
      if (!e.altKey || inHost(e.target as Node)) return;
      stop(e);
      const hits = clicked(e);
      const first = hits[0];
      if (first === undefined) {
        setNote({ x: e.clientX, y: e.clientY });
        setTimeout(() => setNote(null), 1600);
        return;
      }
      const s = shown[first];
      if (s) setOpen({ key: s.key, args: s.args, around: hits.slice(1), x: e.clientX, y: e.clientY });
    };
    const kinds = ["pointerdown", "pointerup", "mousedown", "mouseup", "dblclick", "auxclick"] as const;
    for (const k of kinds) window.addEventListener(k, stop, true);
    window.addEventListener("click", onClick, true);
    const changed = (e: Event) => refresh((e as CustomEvent<string[]>).detail);
    window.addEventListener("oakbox-wording-changed", changed);
    return () => {
      for (const k of kinds) window.removeEventListener(k, stop, true);
      window.removeEventListener("click", onClick, true);
      window.removeEventListener("oakbox-wording-changed", changed);
    };
  }, []);

  const edit = (key: string, n: number | null) => {
    // Shown with the arguments it last had on the screen, if it was.
    let args: Record<string, unknown> | null = n === null ? null : (shown[n]?.args ?? null);
    if (n === null) for (const s of shown) if (s.key === key) args = s.args;
    setOpen({ key, args, around: [], x: window.innerWidth / 2 - 220, y: 80 });
  };

  return (
    <>
      <button type="button" className="ce-toggle" onClick={() => setPanel(!panel)} aria-expanded={panel}>
        ✎ Wording
      </button>
      {panel && <Panel edit={edit} />}
      {note && (
        <div className="ce-note" style={{ left: note.x + 8, top: note.y + 8 }}>
          Not from the wording: your data, or OpenAVMKit's own words
        </div>
      )}
      {open && (
        <EditBox
          key={`${open.key}|${open.x}|${open.y}`}
          open={open}
          close={() => setOpen(null)}
          pick={(n) => {
            const s = shown[n];
            if (s) setOpen({ ...open, key: s.key, args: s.args, around: open.around.filter((x) => x !== n) });
          }}
        />
      )}
    </>
  );
}

const CSS = `
#${HOST} { font: 13px/1.4 system-ui, sans-serif; color: #1d1d1f; }
#${HOST} code { font: 12px ui-monospace, monospace; }
#${HOST} button { font: inherit; cursor: pointer; }
#${HOST} .ce-toggle { position: fixed; left: 10px; bottom: 10px; z-index: 2147483000; padding: 4px 10px;
  background: #fff8c4; border: 1px solid #b59f3b; border-radius: 4px; box-shadow: 0 1px 3px #0003; }
#${HOST} .ce-panel { position: fixed; left: 10px; bottom: 44px; z-index: 2147483000; width: 420px; max-height: 60vh;
  display: flex; flex-direction: column; background: #fff; border: 1px solid #999; border-radius: 4px;
  box-shadow: 0 4px 16px #0004; }
#${HOST} .ce-panel input { margin: 8px; padding: 4px 6px; font: inherit; }
#${HOST} .ce-list { overflow: auto; padding: 0 8px; }
#${HOST} .ce-list button { display: grid; gap: 1px; width: 100%; text-align: left; padding: 4px 6px; border: 0;
  border-bottom: 1px solid #eee; background: none; }
#${HOST} .ce-list button:hover { background: #eef4ff; }
#${HOST} .ce-list span { color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#${HOST} .ce-hint { margin: 0; padding: 6px 8px; color: #666; border-top: 1px solid #eee; }
#${HOST} .ce-box { position: fixed; z-index: 2147483001; width: min(560px, calc(100vw - 16px)); padding: 10px;
  display: grid; gap: 8px; background: #fff; border: 1px solid #888; border-radius: 4px; box-shadow: 0 6px 24px #0005; }
#${HOST} .ce-key { display: flex; gap: 8px; align-items: baseline; justify-content: space-between; }
#${HOST} .ce-uses { color: #666; }
#${HOST} .ce-around { color: #666; }
#${HOST} .ce-around button { margin-right: 4px; border: 0; background: none; color: #0645ad; padding: 0;
  text-decoration: underline; font: 12px ui-monospace, monospace; }
#${HOST} textarea { width: 100%; box-sizing: border-box; font: 13px/1.45 ui-monospace, monospace; padding: 6px;
  resize: vertical; }
#${HOST} .ce-args { color: #555; display: flex; flex-wrap: wrap; gap: 4px 12px; }
#${HOST} .ce-preview { padding: 6px 8px; background: #f6f6f6; border-left: 3px solid #b59f3b; white-space: pre-wrap; }
#${HOST} .ce-bad { padding: 6px 8px; background: #fde8e8; border-left: 3px solid #c0392b; }
#${HOST} .ce-note { position: fixed; z-index: 2147483001; padding: 4px 8px; background: #333; color: #fff;
  border-radius: 3px; pointer-events: none; }
#${HOST} .ce-foot { display: flex; gap: 8px; align-items: center; }
#${HOST} .ce-foot span { flex: 1; color: #777; }
`;

export function start() {
  if (document.getElementById(HOST)) return;
  const host = document.createElement("div");
  host.id = HOST;
  host.dataset.tool = SENTINEL;
  document.body.append(host);
  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.append(style);
  createRoot(host).render(<Editor />);
}
