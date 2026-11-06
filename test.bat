@echo off
rem Builds the UI, then starts the app (it runs no tests: the checks are in docs\RUNNING.md).
call build.bat && call run.bat
