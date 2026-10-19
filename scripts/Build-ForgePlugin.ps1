[CmdletBinding()]
param(
    [string]$ProjectFile,
    [string]$EngineRoot = 'G:\Program Files\EpicGames\UE_5.6',
    [string[]]$DisablePlugin = @(),
    [ValidateRange(1, 8)][int]$CompileJobs = 4
)
$ErrorActionPreference = 'Stop'
# This machine has an unrelated installed Cargo plugin with a missing
# KitBash3dUsdTools module. Keep it out of every ForgeMCP build invocation.
$pluginBuildOptions = @((@('Cargo') + $DisablePlugin | Select-Object -Unique) |
    ForEach-Object { '-DisablePlugin=' + $_ })
$workspaceRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectFile) { $ProjectFile = Join-Path $workspaceRoot 'ForgeMCPDev.uproject' }
$projectPath = (Resolve-Path -LiteralPath $ProjectFile).Path
$projectRoot = Split-Path -Parent $projectPath
$pluginRoot = Join-Path $projectRoot 'Plugins\Forge'
$buildBatch = Join-Path $EngineRoot 'Engine\Build\BatchFiles\Build.bat'
$logs = Join-Path $projectRoot 'Saved\ForgeBuild'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
# UBT emits authoritative toolchain response files without launching native children.
# Direct redirected MSVC steps avoid stalled child console handles on this machine.
& $buildBatch UnrealEditor Win64 Development ('-Project=' + $projectPath) ('-plugin=' + (Join-Path $pluginRoot 'MajesticForge.uplugin')) -NoUBA -NoUBALocal -NoPCH -NoSharedPCH -SkipBuild -UTF8Output @pluginBuildOptions
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
function Start-NativeStep([string]$Executable, [string]$Arguments, [string]$Name) {
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
    $startInfo.Arguments = $Arguments
    $startInfo.WorkingDirectory = Join-Path $EngineRoot 'Engine\Source'
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $step = [System.Diagnostics.Process]::new()
    $step.StartInfo = $startInfo
    if (-not $step.Start()) { throw "$Name could not be started." }
    return [pscustomobject]@{
        Process = $step; Name = $Name
        Stdout = $step.StandardOutput.ReadToEndAsync()
        Stderr = $step.StandardError.ReadToEndAsync()
        Deadline = [DateTime]::UtcNow.AddMinutes(10)
    }
}
function Complete-NativeStep($Job) {
    $step = $Job.Process
    $Name = $Job.Name
    # Wait for this native process, not PowerShell's descendant job tracking.
    while (-not $step.WaitForExit(200)) {
        if ([DateTime]::UtcNow -gt $Job.Deadline) { throw "$Name remains running (PID $($step.Id)); inspect it before retrying." }
    }
    $step.WaitForExit()
    [IO.File]::WriteAllText((Join-Path $logs ($Name + '.stdout.log')), $Job.Stdout.GetAwaiter().GetResult())
    [IO.File]::WriteAllText((Join-Path $logs ($Name + '.stderr.log')), $Job.Stderr.GetAwaiter().GetResult())
    if ($step.ExitCode -ne 0) {
        Get-Content (Join-Path $logs ($Name + '.stdout.log')) -Tail 50
        Get-Content (Join-Path $logs ($Name + '.stderr.log')) -Tail 20
        throw "$Name failed with native exit code $($step.ExitCode)."
    }
    Write-Output "$Name native exit code: 0"
    $step.Dispose()
}
function Invoke-NativeStep([string]$Executable, [string]$Arguments, [string]$Name) {
    Complete-NativeStep (Start-NativeStep $Executable $Arguments $Name)
}
function Complete-NativeBatch($Jobs) {
    $failures = @()
    foreach ($job in $Jobs) {
        try { Complete-NativeStep $job }
        catch { $failures += $_ }
    }
    if ($failures.Count) { throw ($failures -join [Environment]::NewLine) }
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
    if ($moduleName -eq 'MajesticForge') {
        # UBT can leave an old unity response for this explicitly non-unity
        # module; it references a target-specific generated definitions header.
        $responses = @($responses | Where-Object { $_.Name -ne 'Module.MajesticForge.cpp.obj.rsp' })
    }
    if ($responses.Count -lt 1) { throw "UBT emitted no compile commands for plugin module '$moduleName'." }
    $compileBatch = @()
    foreach ($response in $responses) {
        $compileBatch += Start-NativeStep (Join-Path $toolRoot 'cl.exe') ('@"' + $response.FullName + '"') $response.BaseName
        if ($compileBatch.Count -ge $CompileJobs) {
            Complete-NativeBatch $compileBatch
            $compileBatch = @()
        }
    }
    Complete-NativeBatch $compileBatch
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
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "Source\${projectName}Editor.Target.cs"))) {
    # Blueprint-only validation hosts use the installed engine Editor target.
    $editorTarget = 'UnrealEditor'
}
& $buildBatch $editorTarget Win64 Development ('-Project=' + $projectPath) -WaitMutex -NoHotReloadFromIDE -NoUBA -NoUBALocal -NoPCH -NoSharedPCH -UTF8Output @pluginBuildOptions
if ($LASTEXITCODE -ne 0) { throw "Project editor target '$editorTarget' verification failed." }
Write-Output "Compiled project editor target: $editorTarget"
Write-Output "Compiled plugin: $(Join-Path $pluginRoot 'Binaries\Win64\UnrealEditor-MajesticForge.dll')"
