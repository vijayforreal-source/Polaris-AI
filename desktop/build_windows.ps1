param(
  [string]$Version = "1.0.0-rc1",
  [string]$Output = "release\windows\final"
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root
try {
  npm.cmd --prefix frontend run build
  if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
  & .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath $Output\dist --workpath $Output\build desktop\polaris.spec
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
  Write-Host "Release candidate assembled under $Output\dist"
} finally { Pop-Location }
