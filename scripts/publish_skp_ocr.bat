@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo Shwekyin OCR books: build from spellcheck\out\html and push to the web ...
python scripts\build_skp_ocr.py --push
pause
