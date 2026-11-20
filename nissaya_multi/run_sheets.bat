@echo off
rem Opens the list of every sheet of the three Excel files (nissaya-paungsone, nissaya, OCR Books auto) with their pages. Needs Python. Close this window to stop.
cd /d "%~dp0.."
python nissaya_multi\scripts\m_sheets_index.py
start "" http://127.0.0.1:8794/nissaya_multi/sheets_browser.html
python nissaya_multi\scripts\m_server.py 8794
pause
