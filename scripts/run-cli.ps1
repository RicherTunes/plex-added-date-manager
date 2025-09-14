<#
.SYNOPSIS
  Convenience wrapper for the Python CLI on Windows/Unraid PowerShell.

.DESCRIPTION
  Activates a local venv if present and invokes `src/cli.py` with the
  provided flags. Mirrors the Python CLI arguments for consistency.

.EXAMPLE
  ./scripts/run-cli.ps1 -SectionId 1 -Type movie -Date 2024-01-15 -Year 2023 -DryRun

.NOTES
  Requires Python in PATH. Environment variables `PLEX_BASE_URL` and
  `PLEX_TOKEN` can be provided via a `.env` file or passed explicitly.
#>

param(
  [Parameter(Mandatory=$true)][int]$SectionId,
  [ValidateSet(''movie'',''show'',''1'',''2'')] [string]$Type = ''movie'',
  [Parameter(Mandatory=$true)][string]$Date,
  [int]$Year,
  [string]$TitleContains,
  [int[]]$Ids,
  [int]$PageSize = 200,
  [int]$MaxItems,
  [double]$Sleep = 0,
  [double]$MaxPerMinute,
  [switch]$NoLock,
  [switch]$DryRun,
  [string]$BaseUrl,
  [string]$Token
)

$ErrorActionPreference = ''Stop''

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir ''..'')
Set-Location $repoRoot

# Activate venv if present
$venv = Join-Path $repoRoot ''venv''
if (Test-Path (Join-Path $venv ''Scripts/Activate.ps1'')) {
  . (Join-Path $venv ''Scripts/Activate.ps1'')
}

$argsList = @(
  ''src/cli.py'',
  ''--section-id'', $SectionId,
  ''--type'', $Type,
  ''--date'', $Date,
  ''--page-size'', $PageSize
)
if ($Year) { $argsList += @(''--year'', $Year) }
if ($TitleContains) { $argsList += @(''--title-contains'', $TitleContains) }
if ($Ids) { $argsList += @(''--ids''); $argsList += $Ids }
if ($MaxItems) { $argsList += @(''--max-items'', $MaxItems) }
if ($Sleep) { $argsList += @(''--sleep'', $Sleep) }
if ($MaxPerMinute) { $argsList += @(''--max-per-minute'', $MaxPerMinute) }
if ($NoLock) { $argsList += @(''--no-lock'') }
if ($DryRun) { $argsList += @(''--dry-run'') }
if ($BaseUrl) { $argsList += @(''--base-url'', $BaseUrl) }
if ($Token) { $argsList += @(''--token'', $Token) }

python @argsList
