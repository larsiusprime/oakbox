@echo off
rem Edit OAK box's wording live, in the app window (developers; SPEC 6.6, AGENTS.md "Wording").
rem Alt+click any text to edit it: the change is written to web\src\wording\en.json; review it with git diff.
rem Runs the Vite dev server in wording-edit mode (in its own minimised window) and the app on port 8765,
rem with its window showing the dev server's page. Close the app window to stop both.
setlocal
cd /d "%~dp0"
where uv >/dev/null 2>/dev/null || (echo uv is needed: https://docs.astral.sh/uv/ & pause & exit /b 1)
where npm >/dev/null 2>/dev/null || (echo Node.js ^(npm^) is needed: https://nodejs.org/ & pause & exit /b 1)
if not exist web\node_modules (
  echo Installing the web dependencies...
  pushd web & call npm ci & popd
)
start "OAK box wording (Vite)" /min /d "%~dp0web" cmd /c npm run dev:wording -- --port 5173 --strictPort --host 127.0.0.1
uv run python -X utf8 -m oakbox --port 8765 --ui-url http://127.0.0.1:5173
taskkill /fi "WINDOWTITLE eq OAK box wording (Vite)*" /t /f >/dev/null 2>nul
endlocal
