# SORTIFIED one-time setup — also safe to re-run after `git pull` to pick up new dependencies.
# Usage: double-click setup.cmd in the project folder, or run:  .\setup.cmd

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

Step "Checking tools"
foreach ($tool in "python", "node", "npm", "git") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is not installed. Install it first (Python 3.12+, Node 20+, Git)."
    }
}
python --version
node --version

Step "Python environment (engine\.venv)"
if (-not (Test-Path "engine\.venv\Scripts\python.exe")) {
    python -m venv engine\.venv
}
$py = "engine\.venv\Scripts\python.exe"
& $py -m pip install --disable-pip-version-check -q --upgrade pip

# Use the NVIDIA (CUDA) build of PyTorch when this PC has an NVIDIA GPU.
$hasNvidia = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$torchOk = try { & $py -c "import torch; print(torch.cuda.is_available())" 2>$null } catch { "" }
if ($hasNvidia -and $torchOk -ne "True") {
    Step "NVIDIA GPU found - installing CUDA build of PyTorch (large download, once)"
    & $py -m pip install --disable-pip-version-check torch torchvision --index-url https://download.pytorch.org/whl/cu126
}

Step "Python packages"
& $py -m pip install --disable-pip-version-check -q -r engine\requirements.txt -r engine\requirements-dev.txt
& $py -c "import torch; print('PyTorch', torch.__version__, '| GPU:', torch.cuda.is_available())"

Step "UI packages (ui\node_modules)"
Push-Location ui
# `npm ci` installs exactly what package-lock.json lists and never rewrites it.
# (`npm install` can drop optional packages from the lockfile, which breaks CI.)
npm ci --no-audit --no-fund
Pop-Location

Write-Host "`nSetup complete. Start SORTIFIED with: .\dev.cmd" -ForegroundColor Green
