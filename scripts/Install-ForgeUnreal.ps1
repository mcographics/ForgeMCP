[CmdletBinding()]
param(
    [string]$ProjectFile,
    [string]$PackageDirectory
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectFile) { $ProjectFile = Join-Path $workspaceRoot 'ForgeMCPDev.uproject' }
if (-not $PackageDirectory) { $PackageDirectory = Join-Path $workspaceRoot 'Artifacts\ForgeMCP-development-0.2.0\MajesticForge' }
$projectPath = (Resolve-Path -LiteralPath $ProjectFile).Path
$projectRoot = Split-Path -Parent $projectPath
if ([IO.Path]::GetExtension($projectPath) -ne '.uproject') { throw 'Select an Unreal .uproject file.' }
$packageRoot = (Resolve-Path -LiteralPath $PackageDirectory).Path
$pluginDescriptor = Join-Path $packageRoot 'MajesticForge.uplugin'
$pluginDll = Join-Path $packageRoot 'Binaries\Win64\UnrealEditor-MajesticForge.dll'
if (-not (Test-Path -LiteralPath $pluginDescriptor) -or -not (Test-Path -LiteralPath $pluginDll)) {
    throw 'The package must contain MajesticForge.uplugin and its compiled Win64 editor DLL.'
}
$pluginInfo = Get-Content -LiteralPath $pluginDescriptor -Raw | ConvertFrom-Json
if ($pluginInfo.FriendlyName -ne 'ForgeMCP') {
    throw 'This package has an outdated display name. Rebuild it from the current ForgeMCP source before installing.'
}
$project = Get-Content -LiteralPath $projectPath -Raw | ConvertFrom-Json
if ($project.EngineAssociation -ne '5.6') {
    throw 'This binary package was built for Unreal 5.6.1. Build it for your engine version before installing.'
}
$openEditors = @(Get-CimInstance Win32_Process -Filter "Name = 'UnrealEditor.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Replace('/', '\').IndexOf(($projectRoot.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase) -ge 0
})
if ($openEditors.Count) {
    throw 'Save your work and close this project in Unreal first. Its loaded plugin DLL cannot be replaced while the editor is running.'
}
$destination = Join-Path $projectRoot 'Plugins\MajesticForge'
if ($packageRoot.TrimEnd('\') -eq $destination.TrimEnd('\')) { throw 'Package and destination must be separate directories.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
if (Test-Path -LiteralPath $destination) {
    $backupRoot = Join-Path $projectRoot "Saved\MajesticForgeInstallBackups\$stamp"
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination (Join-Path $backupRoot 'MajesticForge') -Recurse
    Write-Output "Previous plugin backed up to $backupRoot"
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Get-ChildItem -LiteralPath $packageRoot | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
}
$entry = @($project.Plugins | Where-Object Name -eq 'MajesticForge')
if ($entry.Count) {
    if ($entry[0].PSObject.Properties.Name -contains 'Enabled') { $entry[0].Enabled = $true }
    else { $entry[0] | Add-Member -NotePropertyName Enabled -NotePropertyValue $true }
} else {
    $plugins = @($project.Plugins | Where-Object { $null -ne $_ }) + @([pscustomobject]@{
        Name = 'MajesticForge'; Enabled = $true; TargetAllowList = @('Editor')
    })
    if ($project.PSObject.Properties.Name -contains 'Plugins') { $project.Plugins = $plugins }
    else { $project | Add-Member -NotePropertyName Plugins -NotePropertyValue $plugins }
}
Copy-Item -LiteralPath $projectPath -Destination ($projectPath + '.backup-' + $stamp)
$project | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $projectPath -Encoding utf8
Write-Output "Installed ForgeMCP in $destination"
Write-Output 'Open your project, then choose Window > ForgeMCP.'
