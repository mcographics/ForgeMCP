[CmdletBinding()]
param([string]$BlenderVersion = '5.2')
$ErrorActionPreference = 'Stop'
if ($BlenderVersion -notmatch '^\d+\.\d+$') { throw 'Use a version such as 5.2.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$addonRoot = Join-Path $projectRoot 'blender-addon\majestic_forge'
$addonSource = Join-Path $addonRoot '__init__.py'
$addonDirectory = Join-Path $env:APPDATA "Blender Foundation\Blender\$BlenderVersion\scripts\addons\majestic_forge"
$destination = Join-Path $addonDirectory '__init__.py'
if ((Test-Path -LiteralPath $destination) -and
    ((Get-FileHash -LiteralPath $destination).Hash -ne (Get-FileHash -LiteralPath $addonSource).Hash)) {
    Copy-Item -LiteralPath $destination -Destination ($destination + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
New-Item -ItemType Directory -Path $addonDirectory -Force | Out-Null
foreach ($module in @('__init__.py', 'security.py', 'automation.py', 'materials.py', 'rigging.py', 'exporting.py', 'transfer_ui.py', 'skinning.py', 'LICENSE.txt')) {
    $moduleSource = Join-Path $addonRoot $module
    $moduleDestination = Join-Path $addonDirectory $module
    if ($module -ne '__init__.py' -and (Test-Path -LiteralPath $moduleDestination) -and
        ((Get-FileHash -LiteralPath $moduleDestination).Hash -ne (Get-FileHash -LiteralPath $moduleSource).Hash)) {
        Copy-Item -LiteralPath $moduleDestination -Destination ($moduleDestination + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    }
    Copy-Item -LiteralPath $moduleSource -Destination $moduleDestination
}
Write-Output "Installed add-on source at $addonDirectory"
Write-Output 'In Blender Preferences > Add-ons, enable ForgeMCP. No preferences were changed by this installer.'
