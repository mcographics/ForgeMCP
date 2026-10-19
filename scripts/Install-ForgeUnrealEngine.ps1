[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EngineRoot,
    [Parameter(Mandatory = $true)][string]$PackageArchive,
    [switch]$Update
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Set up the ForgeMCP Python environment first.' }
$options = @()
if ($Update) { $options += '--update' }
& $python (Join-Path $PSScriptRoot 'install_unreal_engine.py') --engine $EngineRoot --archive $PackageArchive @options
if ($LASTEXITCODE -ne 0) { throw 'Engine-wide ForgeMCP installation failed. Inspect the diagnostic above.' }
