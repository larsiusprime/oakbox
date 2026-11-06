"""Windows: text is UTF-8 everywhere, never the computer's own encoding.

On Windows, Python reads and writes text in the system's code page (cp1252, "charmap") unless told otherwise, so a
"−" in a receipt or an "é" in a column name stops a run there that works everywhere else. Every text read and write
says encoding="utf-8" (this test finds any that don't), and the processes OAK box starts run in Python's UTF-8 mode,
so OpenAVMKit's own reads and writes are UTF-8 too. CI also runs the whole suite with a non-UTF-8 default encoding.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Methods and functions that read or write text in the default encoding unless given one.
TEXT_CALLS = {"open", "read_text", "write_text", "TextIOWrapper", "NamedTemporaryFile", "TemporaryFile", "fdopen"}
# Starting a program: its output is text in the computer's code page when text=True (or universal_newlines) without
# an encoding.
PROCESS_CALLS = {"run", "Popen", "check_output", "call", "check_call"}


def _binary(call: ast.Call) -> bool:
    """open(..., "rb") / mode="wb": bytes, no encoding."""
    modes = [a for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    modes += [k.value for k in call.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
    return any(isinstance(m, ast.Constant) and "b" in str(m.value) for m in modes)


def _missing(path: Path) -> list[str]:
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
        keywords = {k.arg: k.value for k in node.keywords}
        if name in PROCESS_CALLS and "encoding" not in keywords:
            text = [keywords.get(k) for k in ("text", "universal_newlines")]
            if any(isinstance(v, ast.Constant) and v.value is True for v in text):
                out.append(f"{path.relative_to(ROOT)}:{node.lineno}: {ast.unparse(node)[:90]}")
            continue
        if name not in TEXT_CALLS or _binary(node) or any(k.arg == "encoding" for k in node.keywords):
            continue
        # Things called open that aren't files: a web page, a URL.
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("webbrowser", "urllib"):
            continue
        if name in ("NamedTemporaryFile", "TemporaryFile") and not any(
            isinstance(k.value, ast.Constant) and "b" not in str(k.value.value)
            for k in node.keywords
            if k.arg == "mode"
        ):
            continue  # binary unless a text mode is asked for
        out.append(f"{path.relative_to(ROOT)}:{node.lineno}: {ast.unparse(node)[:90]}")
    return out


def test_every_text_read_and_write_says_utf8():
    files = [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py"), *(ROOT / "packaging").rglob("*.py")]
    missing = [m for p in files for m in _missing(p)]
    assert not missing, 'Say encoding="utf-8" (Windows defaults to cp1252):\n' + "\n".join(missing)


def test_processes_oak_box_starts_run_in_utf8_mode():
    """OpenAVMKit's own reads and writes, and what it prints, are UTF-8 in the runs OAK box starts."""
    from oakbox import steps

    env = steps.child_env()
    assert env["PYTHONUTF8"] == "1" and env["PYTHONIOENCODING"] == "utf-8"


def test_saves_at_the_same_time_dont_trip_over_each_other(tmp_path):
    """Two saves of one file at once each use a temporary file of their own (they shared one: the second save found
    it gone, as CI's menu test did when it made a project while the app saved its settings)."""
    import threading

    from oakbox import atomic

    path = tmp_path / "settings.json"
    errors: list[Exception] = []

    def save(i: int) -> None:
        try:
            for _ in range(30):
                atomic.save_text(path, f'{{"n": {i}, "é": "−"}}')
        except Exception as e:  # noqa: BLE001 - collected for the assert
            errors.append(e)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert path.read_text(encoding="utf-8").startswith('{"n": ')
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]  # no temporary files left behind
