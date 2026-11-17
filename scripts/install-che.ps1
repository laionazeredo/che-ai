#Requires -Version 5.1
<#
.SYNOPSIS
    Install or update Che on native Windows, plus the `che` / `che-ai` CLI binaries via pipx.

.DESCRIPTION
    Windows counterpart of scripts/install-che.sh, with the same contract:

      • Default is a DRY RUN. Nothing is written without -Apply.
      • Fresh install copies the whitelist into %USERPROFILE%\.che-ai and moves any pre-existing
        target aside as <target>.bak-<timestamp>.
      • -Update copies item by item and backs up each replaced item instead of the whole tree, so
        files that exist only in the target (your custom skills) are never touched.
      • The blacklist (user_rules/, bindings/registry.jsonl, memory/) is never copied or deleted.
      • hooks.json is rendered per host, never copied raw.
      • The CLI is installed last, and the IDE wiring is delegated to adapters/*/install.ps1.

    Windows has no POSIX symlink guarantee, so the installer copies real files (like the POSIX
    fresh-install path). The Trae adapter decides how the IDE surface is materialised.

.PARAMETER Apply
    Actually write. Without it the script only reports what it would do.

.PARAMETER Update
    Non-destructive update: per-item backup instead of moving the whole target.

.PARAMETER NoCli
    Skip the pipx / pip install of the `che` and `che-ai` binaries.

.PARAMETER Source
    Che checkout to install FROM. Defaults to the current folder, then this script's parent, then
    a shallow clone of the canonical repository.

.PARAMETER Target
    Install destination. Defaults to %USERPROFILE%\.che-ai (legacy %USERPROFILE%\.trae is reused
    when it already holds a Che checkout).

.EXAMPLE
    irm https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.ps1 -OutFile "$env:TEMP\install-che.ps1"
    & "$env:TEMP\install-che.ps1" -Apply

.EXAMPLE
    .\scripts\install-che.ps1 -Apply

.EXAMPLE
    .\scripts\install-che.ps1 -Update -Apply
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param(
    [switch]$Apply,
    [switch]$Update,
    [switch]$NoCli,
    [string]$Source = '',
    [string]$Target = '',
    [string]$RepoUrl = 'https://github.com/laionazeredo/che-ai.git'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Piped execution (irm | iex) has no script scope: $PSScriptRoot is empty and `exit` would close
# the caller's console. Point at the form that works instead of half-running.
if ([string]::IsNullOrEmpty($PSScriptRoot)) {
    Write-Host 'This installer must run as a FILE, not piped into Invoke-Expression.' -ForegroundColor Yellow
    Write-Host 'Piped execution cannot pass -Apply, and its exit codes would close your session.'
    Write-Host ''
    Write-Host '  irm https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.ps1 -OutFile "$env:TEMP\install-che.ps1"'
    Write-Host '  & "$env:TEMP\install-che.ps1"            # dry run'
    Write-Host '  & "$env:TEMP\install-che.ps1" -Apply     # apply'
    return
}

$script:CmdletVar = Get-Variable -Name PSCmdlet -ErrorAction SilentlyContinue
$script:Cmdlet = if ($script:CmdletVar) { $script:CmdletVar.Value } else { $null }
$script:WhatIfVar = Get-Variable -Name WhatIfPreference -ErrorAction SilentlyContinue
$script:WhatIf = if ($script:WhatIfVar) { [bool]$script:WhatIfVar.Value } else { $false }
$script:ApplyRequested = [bool]$Apply
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

function Test-Write {
    param([string]$What)
    if (-not $script:ApplyRequested) { return $false }
    if ($script:Cmdlet) { return $script:Cmdlet.ShouldProcess($What) }
    return (-not $script:WhatIf)
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    Write-Host 'ERROR: this installer targets native Windows.' -ForegroundColor Red
    Write-Host '       On Linux/macOS use scripts/install-che.sh.'
    exit 5
}

$HomeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath('UserProfile') }
if (-not $Target) {
    $Target = Join-Path $HomeDir '.che-ai'
    $legacy = Join-Path $HomeDir '.trae'
    if (-not (Test-Path -LiteralPath $Target) -and (Test-Path -LiteralPath (Join-Path $legacy 'CHE_RULES.md'))) {
        $Target = $legacy
    }
}
$Target = [System.IO.Path]::GetFullPath($Target).TrimEnd('\', '/')

$TempClone = $null
try {
    if (-not $Source) {
        $cwd = (Get-Location).Path
        if (Test-Path -LiteralPath (Join-Path $cwd 'CHE_RULES.md')) {
            $Source = $cwd
        } elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot '..' 'CHE_RULES.md')) {
            $Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
        } else {
            $TempClone = Join-Path ([System.IO.Path]::GetTempPath()) ('che-clone-' + [guid]::NewGuid().ToString('N'))
            Write-Host "-> Cloning Che source from $RepoUrl ..."
            & git clone --depth 1 $RepoUrl $TempClone
            if ($LASTEXITCODE -ne 0) { throw "git clone failed with exit code $LASTEXITCODE" }
            $Source = $TempClone
        }
    }
    $Source = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\', '/')

    if (-not (Test-Path -LiteralPath (Join-Path $Source 'CHE_RULES.md'))) {
        Write-Host "ERROR: '$Source' is not a Che checkout (CHE_RULES.md missing)." -ForegroundColor Red
        exit 2
    }

    $InPlace = ($Source -eq $Target)
    $ModeName = if ($InPlace) { 'in-place (source == target)' }
    elseif ($Update) { 'update (copy, per-item backup)' }
    else { 'fresh-install (copy)' }
    $ModeLabel = if ($Apply) { '[apply]' } else { '[dry-run]' }

    Write-Host '--------------------------------------------------------------'
    Write-Host " Che installer $ModeLabel"
    Write-Host " source : $Source"
    Write-Host " target : $Target"
    Write-Host " mode   : $ModeName"
    Write-Host '--------------------------------------------------------------'

    $BlacklistDirs = @('user_rules', 'memory', '.git', 'node_modules')
    $BlacklistFiles = @('bindings/registry.jsonl')
    $WhitelistRootFiles = @(
        'README.md', 'AGENTS.md', 'CHE_RULES.md', 'CHE_COMMANDS.md', 'REFERENCE_USER_RULES_MINIFIED.md',
        'package.json', 'pnpm-lock.yaml', 'tsconfig.json', 'hooks.json', 'pyproject.toml', '.gitignore'
    )
    $WhitelistDirs = @('che_core', 'commands', 'contracts', 'domains', 'skills', 'hooks', 'scripts', 'adapters', 'permission', 'tests', 'docs')

    # Fail closed: one item may never be both whitelisted and blacklisted.
    foreach ($b in ($BlacklistDirs + $BlacklistFiles)) {
        if (($WhitelistRootFiles + $WhitelistDirs) -contains $b) {
            Write-Host "ERROR: '$b' is BOTH whitelisted and blacklisted - refusing to run." -ForegroundColor Red
            exit 3
        }
    }

    function Sync-File {
        param([string]$Relative, [string]$SourceOverride = '')
        $src = if ($SourceOverride) { $SourceOverride } else { Join-Path $Source $Relative }
        $dst = Join-Path $Target $Relative
        if (-not (Test-Path -LiteralPath $src)) {
            Write-Host "  ${Relative}: missing in source -> SKIP"
            return
        }
        if (Test-Path -LiteralPath $dst) {
            Write-Host "  ${Relative}: backing up -> ${Relative}.bak-$Stamp"
            if (Test-Write "back up $dst") { Move-Item -LiteralPath $dst -Destination "$dst.bak-$Stamp" -Force }
        } else {
            Write-Host "  ${Relative}: + new"
        }
        if (Test-Write "copy $src -> $dst") {
            $parent = Split-Path -Parent $dst
            if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
        }
    }

    function Sync-Dir {
        param([string]$Relative)
        $src = Join-Path $Source $Relative
        $dst = Join-Path $Target $Relative
        if (-not (Test-Path -LiteralPath $src)) {
            Write-Host "  ${Relative}/: missing in source -> SKIP"
            return
        }
        if (-not $Update) {
            Write-Host "  ${Relative}/: copy"
            if (Test-Write "copy $src -> $dst") { Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force }
            return
        }
        if (-not (Test-Path -LiteralPath $dst)) {
            Write-Host "  ${Relative}/: + new dir"
            if (Test-Write "create $dst") { New-Item -ItemType Directory -Path $dst -Force | Out-Null }
        }
        foreach ($child in (Get-ChildItem -LiteralPath $src -Force)) {
            Sync-File (Join-Path $Relative $child.Name)
        }
    }

    if (-not $InPlace -and (Test-Path -LiteralPath $Target)) {
        if ($Update) {
            Write-Host "-> update mode: any replaced item is first moved to <item>.bak-$Stamp."
        } else {
            Write-Host "-> fresh-install: moving existing target -> $Target.bak-$Stamp"
            if (Test-Write "move $Target aside") { Move-Item -LiteralPath $Target -Destination "$Target.bak-$Stamp" -Force }
        }
    }

    if (Test-Write "create $Target") {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $Target 'bindings') -Force | Out-Null
    }

    $python = if (Get-Command py -ErrorAction SilentlyContinue) { @{ Exe = 'py'; Args = @('-3') } }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { @{ Exe = 'python'; Args = @() } }
    else { throw 'Python 3.9+ not found on PATH (neither "py" nor "python").' }

    $renderedHooks = Join-Path ([System.IO.Path]::GetTempPath()) ('che-hooks-' + [guid]::NewGuid().ToString('N') + '.json')
    $renderer = Join-Path $Source 'scripts' 'render_hooks.py'
    & $python.Exe @($python.Args + @($renderer, (Join-Path $Source 'hooks.json'), $renderedHooks, '--harness', $Target, '--platform', 'windows')) | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "render_hooks.py failed with exit code $LASTEXITCODE" }

    try {
        if ($InPlace) {
            Write-Host ' (in-place: content already at target - item sync skipped)'
        } else {
            foreach ($f in $WhitelistRootFiles) {
                $override = if ($f -eq 'hooks.json') { $renderedHooks } else { '' }
                Sync-File $f $override
            }
            foreach ($d in $WhitelistDirs) { Sync-Dir $d }
        }
    } finally {
        if (Test-Path -LiteralPath $renderedHooks) { Remove-Item -LiteralPath $renderedHooks -Force }
    }

    $bindingsReadme = Join-Path $Target 'bindings' 'README.md'
    if (-not (Test-Path -LiteralPath $bindingsReadme) -and (Test-Write "write $bindingsReadme")) {
        $text = @(
            'Level 1 - registry.jsonl.',
            'DO NOT edit manually. Sole writer = contracts helper `che_registry_append_jsonl`.',
            'File is NEVER overwritten by install-che.ps1 or `git pull` (blacklisted).'
        ) -join "`n"
        [System.IO.File]::WriteAllText($bindingsReadme, $text + "`n", (New-Object System.Text.UTF8Encoding($false)))
    }
    foreach ($d in @('user_rules', 'memory')) {
        $full = Join-Path $Target $d
        if (-not (Test-Path -LiteralPath $full) -and (Test-Write "create $full")) {
            New-Item -ItemType Directory -Path $full -Force | Out-Null
            [System.IO.File]::WriteAllText((Join-Path $full '.gitkeep'), '')
        }
    }

    Write-Host ''
    Write-Host " BLACKLIST (untouched in both modes):"
    Write-Host '   - user_rules/              (your personal rules are never copied/deleted)'
    Write-Host '   - bindings/registry.jsonl  (your local level-1 binding)'
    Write-Host '   - memory/                  (local memory data)'
    Write-Host '   - any target-only folder   (custom skills are never touched)'
    Write-Host ''

    if (-not $Apply) {
        Write-Host 'DRY-RUN. Re-run with -Apply to write:'
        Write-Host "  & '$PSCommandPath' -Apply"
    }

    if ($NoCli) {
        Write-Host '--NoCli passed. Skipping CLI install (IDE slash commands still work).'
    } elseif (-not (Test-Write 'install the che CLI')) {
        Write-Host "Would install che-ai CLI globally via: pipx install -e `"$Target`" --force"
    } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
        Write-Host '==> Installing standalone CLI binaries: che-ai, che'
        & pipx install -e $Target --force
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'WARN: pipx install failed. Falling back to pip --user.' -ForegroundColor Yellow
            & $python.Exe @($python.Args + @('-m', 'pip', 'install', '--user', '-e', $Target))
        } else {
            Write-Host 'OK: CLI installed. Run: che --help'
            & pipx ensurepath | Out-Null
        }
    } else {
        Write-Host 'WARN: pipx not found. Install it with: py -3 -m pip install --user pipx' -ForegroundColor Yellow
        & $python.Exe @($python.Args + @('-m', 'pip', 'install', '--user', '-e', $Target))
        Write-Host 'If `che` is not found afterwards, add the pip user Scripts folder to PATH.'
    }

    if ($Apply) {
        $traeAdapter = Join-Path $Target 'adapters' 'trae' 'install.ps1'
        if (Test-Path -LiteralPath $traeAdapter) {
            Write-Host ''
            Write-Host '==> Wiring the Trae IDE adapter'
            $psExe = (Get-Process -Id $PID).Path
            $policy = @()
            if ([System.IO.Path]::GetFileNameWithoutExtension($psExe) -eq 'powershell') { $policy = @('-ExecutionPolicy', 'Bypass') }
            $adapterArgs = @('-NoProfile') + $policy + @('-File', $traeAdapter, '-CheRepo', $Target)
            if ($script:WhatIf) { $adapterArgs += '-WhatIf' }
            & $psExe @adapterArgs
            if ($LASTEXITCODE -ne 0) { Write-Host 'WARN: Trae adapter reported a failure.' -ForegroundColor Yellow }
        }

        Write-Host ''
        Write-Host ' Post-check checklist:'
        Write-Host "  1. Confirm $(Join-Path $Target 'README.md') exists."
        Write-Host "  2. CLI   : che --help   (or che-ai --help)"
        Write-Host '  3. Reopen the Trae IDE so it reloads AGENTS.md, skills/, commands/ and hooks.json.'
        Write-Host '  4. Slash commands (/che-spec, /che-act, /che-ship, ...) remain the primary path.'
        Write-Host "  5. Rollback: rename any <file>.bak-$Stamp back, or run adapters\trae\uninstall.ps1."
        Write-Host ''
        Write-Host 'NOTE: Git hooks (pre-commit / pre-push) are POSIX shell scripts and are not installed'
        Write-Host '      on native Windows. Run `che review` / `che ship` from the CLI instead.'
    }

    exit 0
} finally {
    if ($TempClone -and (Test-Path -LiteralPath $TempClone)) { Remove-Item -LiteralPath $TempClone -Recurse -Force }
}
