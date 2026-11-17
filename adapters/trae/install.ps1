#Requires -Version 5.1
<#
.SYNOPSIS
    Che Trae adapter for native Windows (PowerShell 5.1+ and 7+).

.DESCRIPTION
    Wires the Che checkout into the Trae agent home (%USERPROFILE%\.trae) so the IDE loads the
    same rules, skills, commands and hooks it loads on Linux and macOS. Trae-native artifacts
    (builtin/, mcps/, memory/, permission/, *.json native config) are never touched.

    HOW THE WIRING IS MATERIALISED
      • symlink  — used when the host allows it (Developer Mode or elevated shell). Full parity
                   with the POSIX adapter: the IDE sees upstream changes immediately after a pull.
      • junction — directory fallback, no privilege required. Also live after a pull, because the
                   junction names the upstream directory, not a copy of it.
      • hardlink — file fallback, no privilege required. NOT live after a pull: git replaces the
                   file (write + rename), so the link keeps the old content until the adapter runs
                   again — which `che update` does automatically after every pull.

    A manifest (%USERPROFILE%\.trae\.che-windows-links.json) records what this adapter created,
    because a hardlink is indistinguishable from a real file. Only recorded entries are ever
    refreshed or pruned; anything else in the Trae home belongs to the user.

.PARAMETER CheRepo
    Absolute path of the Che checkout. Defaults to two levels above this script.

.PARAMETER TraeHome
    Trae agent home. Defaults to $env:TRAE_HOME, then %USERPROFILE%\.trae.

.EXAMPLE
    pwsh -File .\adapters\trae\install.ps1 -WhatIf
    pwsh -File .\adapters\trae\install.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param(
    [string]$CheRepo = (Resolve-Path ([System.IO.Path]::Combine($PSScriptRoot, '..', '..'))).Path,
    [string]$TraeHome = $(if ($env:TRAE_HOME) { $env:TRAE_HOME } else { Join-Path $env:USERPROFILE '.trae' })
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:Cmdlet = $PSCmdlet
$script:ManifestName = '.che-windows-links.json'
$script:ManifestPath = Join-Path $TraeHome $script:ManifestName
$script:Entries = @{}

function Test-Mutation {
    param([string]$What)
    return $script:Cmdlet.ShouldProcess($What)
}

function Get-PythonInvocation {
    if (Get-Command py -ErrorAction SilentlyContinue) { return @{ Exe = 'py'; Args = @('-3') } }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @{ Exe = 'python'; Args = @() } }
    throw 'Python 3.9+ not found on PATH (neither "py" nor "python"). Install it from python.org.'
}

function Test-SymlinkSupport {
    param([string]$ProbeDir)
    $stamp = [guid]::NewGuid().ToString('N')
    $target = Join-Path $ProbeDir ".che-probe-target-$stamp"
    $probe = Join-Path $ProbeDir ".che-probe-link-$stamp"
    try {
        [System.IO.File]::WriteAllText($target, 'probe')
        New-Item -ItemType SymbolicLink -Path $probe -Target $target -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        if ([System.IO.File]::Exists($probe) -or (Test-Path -LiteralPath $probe)) { [System.IO.File]::Delete($probe) }
        if ([System.IO.File]::Exists($target)) { [System.IO.File]::Delete($target) }
    }
}

function Get-ExistingEntry {
    param([string]$Path)
    return Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
}

function Test-ReparsePoint {
    param([string]$Path)
    $item = Get-ExistingEntry $Path
    if (-not $item) { return $false }
    return (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Remove-CheEntry {
    param([string]$Path, [string]$Kind)
    $item = Get-ExistingEntry $Path
    if (-not $item) { return }

    if ($Kind -eq 'hardlink') {
        $recorded = $script:Entries[$Path]
        $target = $recorded.target
        if ($target -and [System.IO.File]::Exists($target) -and ([System.IO.FileInfo]::new($target).Length -eq $item.Length)) {
            [System.IO.File]::Delete($Path)
            return
        }
        Write-Host "  ! $Path no longer matches the link we created; leaving it alone"
        return
    }

    if ($item.PSIsContainer) {
        [System.IO.Directory]::Delete($Path, $false)
        return
    }
    [System.IO.File]::Delete($Path)
}

function New-CheEntry {
    param([string]$Path, [string]$Target, [string]$Kind)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    switch ($Kind) {
        'symlink' { New-Item -ItemType SymbolicLink -Path $Path -Target $Target -ErrorAction Stop | Out-Null }
        'junction' { New-Item -ItemType Junction -Path $Path -Target $Target -ErrorAction Stop | Out-Null }
        'hardlink' { New-Item -ItemType HardLink -Path $Path -Target $Target -ErrorAction Stop | Out-Null }
        'copy' { Copy-Item -LiteralPath $Target -Destination $Path -Force }
        default { throw "unknown link kind: $Kind" }
    }
}

function Read-Manifest {
    $result = @{}
    if (-not (Test-Path -LiteralPath $script:ManifestPath)) { return $result }
    $raw = Get-Content -Raw -LiteralPath $script:ManifestPath | ConvertFrom-Json
    if (-not $raw.entries) { return $result }
    foreach ($prop in $raw.entries.PSObject.Properties) {
        $result[$prop.Name] = [pscustomobject]@{ kind = $prop.Value.kind; target = $prop.Value.target }
    }
    return $result
}

function Write-Manifest {
    $body = [ordered]@{ version = 1; entries = [ordered]@{} }
    foreach ($key in ($script:Entries.Keys | Sort-Object)) {
        $body.entries[$key] = [ordered]@{ kind = $script:Entries[$key].kind; target = $script:Entries[$key].target }
    }
    $text = ($body | ConvertTo-Json -Depth 6) + "`n"
    [System.IO.File]::WriteAllText($script:ManifestPath, $text, (New-Object System.Text.UTF8Encoding($false)))
}

function Register-Entry {
    param([string]$Key, [string]$Path, [string]$Target, [string]$Kind, [switch]$Pointer)
    $exists = $null -ne (Get-ExistingEntry $Path)
    $recorded = $script:Entries.ContainsKey($Key)

    if ($exists -and -not $recorded -and -not (Test-ReparsePoint $Path)) {
        if (-not $Pointer) {
            Write-Host "  SKIP: $Path exists and is not a link"
            return $false
        }
        $backup = "$Path.bak"
        Write-Host "  WARN: $Path exists and is not a link. Backing up -> $backup"
        if (Test-Mutation "back up $Path -> $backup") { Move-Item -LiteralPath $Path -Destination $backup -Force }
    } elseif ($exists) {
        Remove-CheEntry $Path $Kind
    }

    if (Test-Mutation "link $Path -> $Target ($Kind)") {
        try {
            New-CheEntry $Path $Target $Kind
            $script:Entries[$Key] = [pscustomobject]@{ kind = $Kind; target = $Target }
        } catch {
            if ($Kind -ne 'hardlink') { throw }
            # A hardlink needs both names on one volume; a profile on D: with the repo on C: is
            # common enough that failing the whole install over it would be the wrong trade.
            Write-Host "  WARN: hardlink failed ($($_.Exception.Message)). Copying instead."
            New-CheEntry $Path $Target 'copy'
            $script:Entries[$Key] = [pscustomobject]@{ kind = 'copy'; target = $Target }
        }
    }
    return $true
}

if (-not (Test-Path -LiteralPath $TraeHome)) {
    Write-Host "SKIP: Trae home not found at $TraeHome (Trae IDE not installed). Nothing to wire."
    exit 0
}
if (-not (Test-Path -LiteralPath (Join-Path $CheRepo 'CHE_RULES.md'))) {
    Write-Host "ERROR: '$CheRepo' is not a Che checkout (CHE_RULES.md missing)." -ForegroundColor Red
    exit 2
}

$fileKind = if (Test-SymlinkSupport $TraeHome) { 'symlink' } else { 'hardlink' }
$dirKind = if ($fileKind -eq 'symlink') { 'symlink' } else { 'junction' }

Write-Host 'Che Trae adapter (Windows)'
Write-Host "  Che repo   : $CheRepo"
Write-Host "  Trae home  : $TraeHome"
Write-Host "  link mode  : $fileKind (directories: $dirKind)"

$script:Entries = Read-Manifest

# Prune first: an upstream rename leaves a link pointing at nothing, and the loops below only
# walk what exists now — so the orphan would survive every re-install otherwise.
foreach ($key in @($script:Entries.Keys)) {
    if (Test-Path -LiteralPath $script:Entries[$key].target) { continue }
    Write-Host "  - orphan removed: $key"
    if (Test-Mutation "remove orphan $key") {
        Remove-CheEntry $key $script:Entries[$key].kind
        $script:Entries.Remove($key)
    }
}

$pointers = @(
    @{ Key = 'AGENTS.md'; Target = Join-Path $CheRepo 'AGENTS.md'; Dir = $false },
    @{ Key = 'CHE_RULES.md'; Target = Join-Path $CheRepo 'CHE_RULES.md'; Dir = $false },
    @{ Key = 'CHE_COMMANDS.md'; Target = Join-Path $CheRepo 'CHE_COMMANDS.md'; Dir = $false },
    @{ Key = 'domains'; Target = Join-Path $CheRepo 'domains'; Dir = $true },
    @{ Key = 'user_rules'; Target = Join-Path $CheRepo 'user_rules'; Dir = $true }
)
foreach ($pointer in $pointers) {
    if (-not (Test-Path -LiteralPath $pointer.Target)) {
        Write-Host "  SKIP: $($pointer.Key) (source missing: $($pointer.Target))"
        continue
    }
    $kind = if ($pointer.Dir) { $dirKind } else { $fileKind }
    $ok = Register-Entry -Key (Join-Path $TraeHome $pointer.Key) -Path (Join-Path $TraeHome $pointer.Key) `
        -Target $pointer.Target -Kind $kind -Pointer
    if ($ok) { Write-Host "  -> $($pointer.Key)" }
}

$collections = @(
    @{ Source = (Join-Path $CheRepo 'skills'); Dest = (Join-Path $TraeHome 'skills'); Dir = $true; Filter = '*' },
    @{ Source = (Join-Path $CheRepo 'commands'); Dest = (Join-Path $TraeHome 'commands'); Dir = $false; Filter = '*.md' },
    @{ Source = (Join-Path $CheRepo 'hooks'); Dest = (Join-Path $TraeHome 'hooks'); Dir = $false; Filter = '*.py' }
)
$counts = @{}
foreach ($collection in $collections) {
    $linked = 0
    if (Test-Path -LiteralPath $collection.Source) {
        foreach ($item in (Get-ChildItem -LiteralPath $collection.Source -Filter $collection.Filter -Force)) {
            if ($collection.Dir -and -not $item.PSIsContainer) { continue }
            if (-not $collection.Dir -and $item.PSIsContainer) { continue }
            if ($collection.Dir -and -not (Test-Path -LiteralPath (Join-Path $item.FullName 'SKILL.md'))) { continue }
            $kind = if ($collection.Dir) { $dirKind } else { $fileKind }
            $dest = Join-Path $collection.Dest $item.Name
            if (Register-Entry -Key $dest -Path $dest -Target $item.FullName -Kind $kind) { $linked++ }
        }
    }
    $counts[$collection.Dest] = $linked
}

# hooks.json is a rendered copy, never a link: the source is a template holding
# __HARNESS_TARGET__ and a platform-specific command form.
$python = Get-PythonInvocation
$renderer = [System.IO.Path]::Combine($CheRepo, 'scripts', 'render_hooks.py')
$rendered = Join-Path ([System.IO.Path]::GetTempPath()) ("che-hooks-" + [guid]::NewGuid().ToString('N') + '.json')
$hooksConfig = Join-Path $TraeHome 'hooks.json'
try {
    & $python.Exe @($python.Args + @($renderer, (Join-Path $CheRepo 'hooks.json'), $rendered, '--harness', $CheRepo, '--platform', 'windows')) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "render_hooks.py failed with exit code $LASTEXITCODE" }

    $current = if ([System.IO.File]::Exists($hooksConfig)) { [System.IO.File]::ReadAllText($hooksConfig) } else { '' }
    $next = [System.IO.File]::ReadAllText($rendered)
    if ($current -eq $next) {
        Write-Host '  = hooks.json unchanged'
    } elseif (Test-Mutation "write $hooksConfig") {
        if (Test-Path -LiteralPath $hooksConfig) {
            if (Test-ReparsePoint $hooksConfig) {
                Remove-CheEntry $hooksConfig 'symlink'
            } else {
                $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
                Move-Item -LiteralPath $hooksConfig -Destination "$hooksConfig.bak-$stamp" -Force
                Write-Host "  ~ hooks.json (previous -> $hooksConfig.bak-$stamp)"
            }
        }
        [System.IO.File]::WriteAllText($hooksConfig, $next, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host '  + hooks.json rendered'
    }
    $script:Entries[$hooksConfig] = [pscustomobject]@{ kind = 'rendered'; target = $hooksConfig }
} finally {
    if ([System.IO.File]::Exists($rendered)) { [System.IO.File]::Delete($rendered) }
}

if (Test-Mutation "write $script:ManifestPath") { Write-Manifest }

Write-Host ''
Write-Host 'Che - Trae adapter installed.'
Write-Host "  skills/   : $($counts[(Join-Path $TraeHome 'skills')])"
Write-Host "  commands/ : $($counts[(Join-Path $TraeHome 'commands')])"
Write-Host "  hooks/    : $($counts[(Join-Path $TraeHome 'hooks')])  (+ hooks.json)"
Write-Host ''
if ($WhatIfPreference) { Write-Host 'WhatIf: nothing was written (dry run).' }
if ($fileKind -eq 'hardlink') {
    Write-Host 'NOTE: file links are hardlinks (no Developer Mode). They refresh on `che update`,'
    Write-Host '      not on a bare `git pull`. Enable Developer Mode for symlink parity.'
}
Write-Host "For this Che checkout in this shell:  `$env:CHE_HOME = '$CheRepo'"
exit 0
