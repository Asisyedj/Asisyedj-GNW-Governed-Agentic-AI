@echo off
setlocal
cd /d "D:\GNW\perplexity-browser-api"
echo ==== GNW SECURE BRIDGE START %DATE% %TIME% ====>> "D:\GNW\perplexity-browser-api\bridge-secure.log"
"D:\GNW\perplexity-browser-api\.venv\Scripts\python.exe" -u "D:\GNW\perplexity-browser-api\bridge_daemon.py" >> "D:\GNW\perplexity-browser-api\bridge-secure.log" 2>&1
set "RC=%ERRORLEVEL%"
echo BRIDGE_EXIT_CODE=%RC%>> "D:\GNW\perplexity-browser-api\bridge-secure.log"
exit /b %RC%
