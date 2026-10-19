[CmdletBinding()]
param(
    [string]$ProjectFile,
    [string]$PackageDirectory,
    [string]$PackageArchive
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectFile) { $ProjectFile = Join-Path $workspaceRoot 'ForgeMCPDev.uproject' }
if ($PackageDirectory -and $PackageArchive) { throw 'Choose PackageDirectory or PackageArchive, not both.' }
$projectPath = (Resolve-Path -LiteralPath $ProjectFile).Path
$projectRoot = Split-Path -Parent $projectPath
if ([IO.Path]::GetExtension($projectPath) -ne '.uproject') { throw 'Select an Unreal .uproject file.' }
$openEditors = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe') -and $_.CommandLine -and
    $_.CommandLine.Replace('/', '\').IndexOf(($projectRoot.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase) -ge 0
})
if ($openEditors.Count) { throw 'Save your work and close this project in Unreal first. Its plugin cannot be replaced while the editor is running.' }
if (-not $PackageDirectory) {
    if (-not $PackageArchive) {
        $sourceDescriptor = Join-Path $workspaceRoot 'Plugins\Forge\MajesticForge.uplugin'
        $sourceInfo = Get-Content -LiteralPath $sourceDescriptor -Raw | ConvertFrom-Json
        $channel = if ($sourceInfo.VersionName -like '*-alpha.*') { 'Alpha' } else { 'Development' }
        $packageName = 'ForgeMCP-Unreal-{0}-{1}-UE5.6.1-Win64.zip' -f $channel, $sourceInfo.VersionName
        $PackageArchive = Join-Path $workspaceRoot ('Artifacts\' + $packageName)
    }
    $archivePath = (Resolve-Path -LiteralPath $PackageArchive).Path
    $python = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'The ForgeMCP Python environment is required to validate this archive. Set it up first, or use an independently verified extracted PackageDirectory.' }
    $staging = Join-Path $projectRoot ('Saved\ForgeInstallStaging\' + [Guid]::NewGuid().ToString('N'))
    & $python (Join-Path $PSScriptRoot 'extract_unreal_package.py') --archive $archivePath --destination $staging
    if ($LASTEXITCODE -ne 0) { throw 'Archive validation failed; the project plugin was not modified.' }
    $PackageDirectory = Join-Path $staging 'Forge'
}
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
$destination = Join-Path $projectRoot 'Plugins\Forge'
if ($packageRoot.TrimEnd('\') -eq $destination.TrimEnd('\')) { throw 'Package and destination must be separate directories.' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
if (Test-Path -LiteralPath $destination) {
    $backupRoot = Join-Path $projectRoot "Saved\MajesticForgeInstallBackups\$stamp"
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination (Join-Path $backupRoot 'Forge') -Recurse
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
