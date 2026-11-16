#Requires -Version 5.1
<#
.SYNOPSIS
    Roll back the Che Trae adapter on native Windows.

.DESCRIPTION
    Removes only what install.ps1 recorded in %USERPROFILE%\.trae\.che-windows-links.json: the
    links it created, the hooks.json it rendered, and the manifest itself. Trae-native artifacts and
    any real file the user put there are never touched. A pointer file that was backed up during
    install (AGENTS.md.bak, CHE_RULES.md.bak, ...) is restored in place.

    No manifest means nothing to roll back: the Windows adapter never ran against this Trae home.
    A POSIX install (symlinks created by adapters/trae/install.sh under Git Bash or WSL) is removed
    by adapters/trae/uninstall.sh, not by this script.

.EXAMPLE
    pwsh -File .\adapters\trae\uninstall.ps1 -WhatIf
    pwsh -File .\adapters\trae\uninstall.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param(
    [string]$TraeHome = $(if ($env:TRAE_HOME) { $env:TRAE_HOME } else { Join-Path $env:USERPROFILE '.trae' })
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:Cmdlet = $PSCmdlet
$manifestPath = Join-Path $TraeHome '.che-windows-links.json'

function Test-Mutation {
    param([string]$What)
    return $script:Cmdlet.ShouldProcess($What)
}

Write-Host 'Uninstalling Che Trae adapter (Windows)...'
Write-Host "  Trae home : $TraeHome"

if (-not (Test-Path -LiteralPath $TraeHome)) {
    Write-Host "SKIP: Trae home not found at $TraeHome. Nothing to remove."
    exit 0
}
if (-not (Test-Path -LiteralPath $manifestPath)) {
    Write-Host 'SKIP: no .che-windows-links.json - this adapter never installed here.'
    exit 0
}

$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$entries = @()
if ($manifest.entries) { $entries = @($manifest.entries.PSObject.Properties) }

$pointers = @('AGENTS.md', 'CHE_RULES.md', 'CHE_COMMANDS.md', 'domains', 'user_rules')
$hooksConfig = Join-Path $TraeHome 'hooks.json'
$removed = 0

foreach ($entry in $entries) {
    $path = $entry.Name
    if ($entry.Value.kind -eq 'rendered') { continue }

    $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if (-not $item) { continue }

    if (Test-Mutation "remove $path") {
        if ($item.PSIsContainer) {
            [System.IO.Directory]::Delete($path, $false)
        } else {
            [System.IO.File]::Delete($path)
        }
        $removed++
        Write-Host "  - $path"
    }

    $leaf = Split-Path -Leaf $path
    if ($pointers -contains $leaf) {
        $backup = "$path.bak"
        if (Test-Path -LiteralPath $backup) {
            if (Test-Mutation "restore $backup -> $path") {
                Move-Item -LiteralPath $backup -Destination $path -Force
                Write-Host "  <- $leaf (restored .bak)"
            }
        }
    }
}

# hooks.json is moved aside rather than deleted: it may carry hand edits made after install, and
# the POSIX uninstaller takes the same conservative route.
if (Test-Path -LiteralPath $hooksConfig) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    if (Test-Mutation "move $hooksConfig aside") {
        Move-Item -LiteralPath $hooksConfig -Destination "$hooksConfig.removed-$stamp" -Force
        Write-Host "  hooks.json moved -> $hooksConfig.removed-$stamp"
    }
}

if (Test-Mutation "remove $manifestPath") { Remove-Item -LiteralPath $manifestPath -Force }

Write-Host ''
Write-Host "Che - Trae adapter removed. Entries removed: $removed"
exit 0
