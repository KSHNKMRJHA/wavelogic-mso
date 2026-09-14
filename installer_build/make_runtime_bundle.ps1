# WaveLogic MSO - runtime bundle builder
# Layout:
#   dist_runtime\
#     WaveLogicMSO.exe            (compiled launcher, optional during early smoke tests)
#     app.py, analyzer_core.py, branding.py, pages\, sample_data\, .streamlit\
#     wavelogic_logo.png / wavelogic_logo.ico
#     python\
#       python.exe, python312.dll, python3.dll, vcruntime140*.dll
#       DLLs\, Lib\ (stdlib subset), Lib\site-packages (venv packages, pruned)
param(
    [string]$Root = "C:\Users\Lenovo\Downloads\osci_calc\osci_calc\installer_build",
    [switch]$SkipLauncher
)

$ErrorActionPreference = "Stop"
$BASE_PY = "C:\Users\Lenovo\AppData\Local\Programs\Python\Python312"
$VENV_SP = "C:\Users\Lenovo\Downloads\osci_calc\osci_calc\.venv\Lib\site-packages"
$SRC = "$Root\src"
$DST = "$Root\dist_runtime"
$PYDST = "$DST\python"

function Copy-Tree {
    param([string]$From, [string]$To, [string[]]$Exclude)
    if (-not (Test-Path $From)) { return }
    foreach ($item in Get-ChildItem $From -Force) {
        if ($Exclude -contains $item.Name) { continue }
        Copy-Item $item.FullName -Destination $To -Recurse -Force -ErrorAction Stop
    }
}

Write-Output "[1/5] cleaning dist_runtime"
if (Test-Path $DST) { Remove-Item $DST -Recurse -Force }
New-Item -ItemType Directory -Path $DST -Force | Out-Null

Write-Output "[2/5] python core (exe, dlls, stdlib subset)"
New-Item -ItemType Directory -Path "$PYDST\DLLs" -Force | Out-Null
New-Item -ItemType Directory -Path "$PYDST\Lib" -Force | Out-Null
foreach ($f in "python.exe","pythonw.exe","python3.dll","python312.dll","vcruntime140.dll","vcruntime140_1.dll","LICENSE.txt") {
    if (Test-Path "$BASE_PY\$f") { Copy-Item "$BASE_PY\$f" -Destination $PYDST -Force }
}
Copy-Item "$BASE_PY\DLLs\*" -Destination "$PYDST\DLLs" -Recurse -Force
Copy-Tree -From "$BASE_PY\Lib" -To "$PYDST\Lib" -Exclude @("test","idlelib","lib2to3","turtledemo","ensurepip","site-packages","__phello__","msilib")

Write-Output "[3/5] site-packages (venv, pruned)"
New-Item -ItemType Directory -Path "$PYDST\Lib\site-packages" -Force | Out-Null
Copy-Tree -From $VENV_SP -To "$PYDST\Lib\site-packages" -Exclude @("nuitka","nuitka-4.2.1.dist-info","pip","pip-26.2.1.dist-info")

Write-Output "[4/5] app files + layouts"
Copy-Item "$SRC\app.py","$SRC\analyzer_core.py","$SRC\branding.py","$SRC\wavelogic_logo.png","$SRC\wavelogic_logo.ico" -Destination $DST -Force
if (Test-Path "$SRC\pages") { Copy-Item "$SRC\pages" -Destination $DST -Recurse -Force }
if (Test-Path "$SRC\sample_data") { Copy-Item "$SRC\sample_data" -Destination $DST -Recurse -Force }
if (Test-Path "$SRC\.streamlit") { Copy-Item "$SRC\.streamlit" -Destination $DST -Recurse -Force }
if (-not $SkipLauncher) {
    $srcDist = "$Root\dist\launcher.dist"
    if (Test-Path "$srcDist\launcher.exe") {
        Write-Output "  copying launcher bundle (exe + tk/PIL data) -> dist_runtime"
        Copy-Item "$srcDist\*" -Destination $DST -Recurse -Force
        if (Test-Path "$DST\launcher.exe") { Rename-Item "$DST\launcher.exe" "WaveLogicMSO.exe" -Force }
    }
    else { Write-Warning "launcher.dist missing - skipping launcher copy" }
}

Write-Output "[5/5] summary"
$tot = (Get-ChildItem $DST -Recurse -File | Measure-Object Length -Sum).Sum
Write-Output ("dist_runtime total: {0:N0} MB" -f ($tot/1MB))
Write-Output "STAGING DONE"