/** The live copy editor's start (SPEC §6.6), first thing on the page; in every build but `npm run dev:copy` this
 * is empty (`__COPY_EDIT__` is false, and the code below is dropped). Markers never leave the page: they're taken
 * out of every request, of what's copied, and of the window title. The editor itself loads after. */
import { hasMarks, strip } from "../marks";

if (__COPY_EDIT__) {
  const fetch0 = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    let i: RequestInfo | URL = input;
    let o = init;
    if (typeof i === "string" && hasMarks(i)) i = strip(i);
    if (o && typeof o.body === "string" && hasMarks(o.body)) o = { ...o, body: strip(o.body) };
    if (i instanceof Request) {
      const url = hasMarks(i.url) ? strip(i.url) : i.url;
      if (i.body && !["GET", "HEAD"].includes(i.method)) {
        const body = await i.clone().text();
        if (hasMarks(body) || url !== i.url)
          i = new Request(url, { method: i.method, headers: i.headers, body: strip(body) });
      } else if (url !== i.url) i = new Request(url, i);
    }
    return fetch0(i, o);
  };
  const write0 = navigator.clipboard?.writeText?.bind(navigator.clipboard);
  if (write0) navigator.clipboard.writeText = (s: string) => write0(strip(s));
  document.addEventListener("copy", (e) => {
    const s = document.getSelection()?.toString() ?? "";
    if (!hasMarks(s) || !e.clipboardData) return;
    e.clipboardData.setData("text/plain", strip(s));
    e.preventDefault();
  });
  // The title as the app set it (with its markers) is kept for the editor's list.
  const title = () => {
    const now = document.title;
    if (!hasMarks(now)) return;
    (window as { __copyTitle?: string }).__copyTitle = now;
    document.title = strip(now);
  };
  new MutationObserver(title).observe(document.head, { subtree: true, childList: true, characterData: true });
  void import("./editor").then((m) => m.start());
}
