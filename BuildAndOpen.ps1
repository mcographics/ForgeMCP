[CmdletBinding()]
param(
    [string]$EngineRoot,
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
$projectPath = Join-Path $PSScriptRoot 'ForgeMCPDev.uproject'
$project = Get-Content -LiteralPath $projectPath -Raw | ConvertFrom-Json

if (-not $EngineRoot) {
    $engineRegistry = Get-ItemProperty -LiteralPath "HKLM:\SOFTWARE\EpicGames\Unreal Engine\$($project.EngineAssociation)" -ErrorAction SilentlyContinue
    $EngineRoot = $engineRegistry.InstalledDirectory
}
if (-not $EngineRoot) {
    throw 'Unreal Engine was not found. Pass -EngineRoot with the UE installation folder.'
}

$buildScript = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
$editorPath = Join-Path $EngineRoot 'Engine\Binaries\Win64\UnrealEditor.exe'
$cacheRules = Join-Path $EngineRoot 'Engine\Source\Developer\DerivedDataCache\DerivedDataCache.Build.cs'
foreach ($requiredFile in @($buildScript, $editorPath, $cacheRules)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Unreal Engine installation is missing: $requiredFile`nOpen Epic Games Launcher > Unreal Engine > Library > this engine's dropdown > Verify, then retry."
    }
}

& $buildScript ForgeMCPDevEditor Win64 Development "-Project=$projectPath" -WaitMutex -NoHotReloadFromIDE
if ($LASTEXITCODE -ne 0) {
    throw "Unreal build failed (exit code $LASTEXITCODE). See $env:LOCALAPPDATA\UnrealBuildTool\Log.txt."
}

if (-not $BuildOnly) {
    # This is the interactive editor the user requested to open.
    Start-Process -FilePath $editorPath -ArgumentList ('"{0}"' -f $projectPath)
}
