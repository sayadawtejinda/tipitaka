@echo off
cd /d "%~dp0"
start "" http://127.0.0.1:8796/
python -X utf8 scripts\sbs_review_server.py
pause
