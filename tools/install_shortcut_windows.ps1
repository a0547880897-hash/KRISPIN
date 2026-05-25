# יוצר קיצור דרך "YouTube Downloader" על שולחן העבודה (Windows)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "YouTube Downloader.lnk"

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
$sc.TargetPath = Join-Path $root "start.bat"
$sc.WorkingDirectory = $root
$sc.IconLocation = (Join-Path $root "assets\icon.ico")
$sc.Description = "הורדת סרטוני יוטיוב באיכות מקסימלית"
$sc.Save()

Write-Host "✅ נוצר קיצור דרך על שולחן העבודה: YouTube Downloader"
