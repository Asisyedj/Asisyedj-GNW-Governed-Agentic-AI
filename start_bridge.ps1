$ErrorActionPreference = 'Stop'
$Root = 'D:\GNW\perplexity-browser-api'
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Entry = Join-Path $Root 'bridge_daemon.py'
if (!(Test-Path -LiteralPath $Python) -or !(Test-Path -LiteralPath $Entry)) { throw 'GNW bridge runtime file missing.' }
$p = Start-Process -FilePath $Python -ArgumentList @($Entry) -WorkingDirectory $Root -WindowStyle Hidden -PassThru
Add-Content -LiteralPath (Join-Path $Root 'bridge-startup.log') -Value ("[{0:o}] Bridge process launched; pid={1}; bound address is enforced by bridge_daemon.py." -f (Get-Date), $p.Id)
