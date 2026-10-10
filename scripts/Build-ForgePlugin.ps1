[CmdletBinding()]
param(
    [string]$ProjectFile,
    [string]$EngineRoot = 'G:\Program Files\EpicGames\UE_5.6'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectFile) { $ProjectFile = Join-Path $workspaceRoot 'ForgeMCPDev.uproject' }
$projectPath = (Resolve-Path -LiteralPath $ProjectFile).Path
$projectRoot = Split-Path -Parent $projectPath
$pluginRoot = Join-Path $projectRoot 'Plugins\MajesticForge'
$buildBatch = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
$logs = Join-Path $projectRoot 'Saved\ForgeBuild'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
# UBT emits authoritative toolchain response files without launching native children.
# Direct redirected MSVC steps avoid stalled child console handles on this machine.
& $buildBatch UnrealEditor Win64 Development ('-Project=' + $projectPath) ('-plugin=' + (Join-Path $pluginRoot 'MajesticForge.uplugin')) -NoUBA -NoUBALocal -NoPCH -NoSharedPCH -SkipBuild -UTF8Output
if ($LASTEXITCODE -ne 0) { throw 'Unreal build graph/header generation failed.' }
$pluginDescriptor = Get-Content -LiteralPath (Join-Path $pluginRoot 'MajesticForge.uplugin') -Raw | ConvertFrom-Json
$moduleBuildRoot = Join-Path $pluginRoot 'Intermediate\Build\Win64\x64\UnrealEditor\Development'
$moduleOrder = @($pluginDescriptor.Modules | Sort-Object @{ Expression = {
    switch ($_.Type) {
        'Runtime' { 0 }
        'Developer' { 1 }
        'Editor' { 2 }
        default { 1 }
    }
} }, Name)
if ($moduleOrder.Count -lt 1) { throw 'The plugin descriptor contains no build modules.' }
# Discover the exact compiler selected by this installed engine build.
$sdkTools = & 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe' -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$toolRoot = Join-Path $sdkTools 'VC\Tools\MSVC\14.38.33130\bin\Hostx64\x64'
if (-not (Test-Path -LiteralPath (Join-Path $toolRoot 'cl.exe'))) { throw 'This UE 5.6 validation build requires the verified MSVC 14.38.33130 toolchain.' }
function Invoke-NativeStep([string]$Executable, [string]$Arguments, [string]$Name) {
    $step = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory (Join-Path $EngineRoot 'Engine\Source') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs ($Name + '.stdout.log')) -RedirectStandardError (Join-Path $logs ($Name + '.stderr.log'))
    # Wait for this native process, not PowerShell's descendant job tracking, which
    # can remain blocked after an already-exited compiler on this host.
    $deadline = [DateTime]::UtcNow.AddMinutes(10)
    while (-not $step.WaitForExit(200)) {
        if ([DateTime]::UtcNow -gt $deadline) { throw "$Name remains running (PID $($step.Id)); inspect it before retrying." }
    }
    if ($step.ExitCode -ne 0) {
        Get-Content (Join-Path $logs ($Name + '.stdout.log')) -Tail 50
        Get-Content (Join-Path $logs ($Name + '.stderr.log')) -Tail 20
        throw "$Name failed with native exit code $($step.ExitCode)."
    }
    Write-Output "$Name native exit code: 0"
}
$resourceCompiler = 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\rc.exe'
New-Item -ItemType Directory -Path (Join-Path $pluginRoot 'Binaries\Win64') -Force | Out-Null
foreach ($module in $moduleOrder) {
    $moduleName = [string]$module.Name
    $responseRoot = Join-Path $moduleBuildRoot $moduleName
    if (-not (Test-Path -LiteralPath $responseRoot)) {
        throw "UBT did not emit response files for plugin module '$moduleName'."
    }
    $responses = @(Get-ChildItem -LiteralPath $responseRoot -Filter '*.obj.rsp')
    if ($responses.Count -lt 1) { throw "UBT emitted no compile commands for plugin module '$moduleName'." }
    foreach ($response in $responses) {
        Invoke-NativeStep (Join-Path $toolRoot 'cl.exe') ('@"' + $response.FullName + '"') $response.BaseName
    }
    foreach ($response in @(Get-ChildItem -LiteralPath $responseRoot -Filter '*.res.rsp')) {
        Invoke-NativeStep $resourceCompiler ((Get-Content -LiteralPath $response.FullName) -join ' ') $response.BaseName
    }
    Invoke-NativeStep (Join-Path $toolRoot 'link.exe') ('/LIB @"' + (Join-Path $responseRoot "UnrealEditor-$moduleName.lib.rsp") + '"') "$moduleName library"
    Invoke-NativeStep (Join-Path $toolRoot 'link.exe') ('@"' + (Join-Path $responseRoot "UnrealEditor-$moduleName.dll.rsp") + '"') "$moduleName dll"
}
$dotnet = Join-Path $EngineRoot 'Engine\Binaries\ThirdParty\DotNet\8.0.300\win-x64\dotnet.exe'
$ubt = Join-Path $EngineRoot 'Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.dll'
$metadata = Join-Path $projectRoot 'Intermediate\Build\Win64\x64\UnrealEditor\Development\TargetMetadata.dat'
Invoke-NativeStep $dotnet ('"' + $ubt + '" -Mode=WriteMetadata "-Input=' + $metadata + '" -Version=2') 'metadata'
$projectName = [IO.Path]::GetFileNameWithoutExtension($projectPath)
$editorTarget = "${projectName}Editor"
& $buildBatch $editorTarget Win64 Development ('-Project=' + $projectPath) -WaitMutex -NoHotReloadFromIDE -UTF8Output
if ($LASTEXITCODE -ne 0) { throw "Project editor target '$editorTarget' verification failed." }
Write-Output "Compiled project editor target: $editorTarget"
Write-Output "Compiled plugin: $(Join-Path $pluginRoot 'Binaries\Win64\UnrealEditor-MajesticForge.dll')"
