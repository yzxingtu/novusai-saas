<#
.SYNOPSIS
    Windsurf Cunzhi Installation Script
.DESCRIPTION
    Install Windsurf Cunzhi (GUI input tool via run_command)
.PARAMETER InstallPath
    Installation path, defaults to user local directory
.PARAMETER NoBuild
    Skip build, use existing executable
#>
param(
    [string]$InstallPath = "$env:LOCALAPPDATA\windsurf-cunzhi",
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Info { param($m) Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok { param($m) Write-Host "[OK] $m" -ForegroundColor Green }
function Write-Err { param($m) Write-Host "[ERROR] $m" -ForegroundColor Red }
function Write-Warn { param($m) Write-Host "[WARN] $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "        Windsurf Cunzhi - Installer                         " -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""

# Define file paths (single binary mode)
# Check same directory first (for release packages), then build output
$mcpExeSameDir = Join-Path $scriptDir "windsurf-cunzhi.exe"
$mcpExeBuild = Join-Path $scriptDir "target\release\windsurf-cunzhi.exe"

if (Test-Path $mcpExeSameDir) {
    $mcpExe = $mcpExeSameDir
    Write-Ok "Found executable in package: $mcpExe"
} elseif (Test-Path $mcpExeBuild) {
    $mcpExe = $mcpExeBuild
    Write-Ok "Found executable in build output: $mcpExe"
} else {
    $mcpExe = $mcpExeBuild
}

# Setup Rust environment
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"

# Check pre-compiled files
$hasMcpExe = Test-Path $mcpExe

# Build (Tauri GUI application)
if (-not $hasMcpExe -and -not $NoBuild) {
    Write-Info "Building windsurf-cunzhi (GUI)..."
    
    $rustVersion = & rustc --version 2>$null
    if (-not $rustVersion) {
        Write-Err "Rust not found. Please install: https://rustup.rs"
        exit 1
    }
    Write-Ok "Rust: $rustVersion"
    
    # Check Node.js (for frontend build)
    $npmVersion = & npm --version 2>$null
    if (-not $npmVersion) {
        Write-Err "Node.js/npm not found. Please install: https://nodejs.org"
        exit 1
    }
    Write-Ok "npm: $npmVersion"
    
    Push-Location $scriptDir
    try {
        Write-Info "Installing npm dependencies..."
        & npm install
        
        Write-Info "Building frontend..."
        & npm run build
        if ($LASTEXITCODE -ne 0) { Write-Err "Frontend build failed"; exit 1 }
        
        Write-Info "Building Tauri application..."
        & cargo tauri build
        if ($LASTEXITCODE -ne 0) { Write-Err "Build failed"; exit 1 }
        Write-Ok "Build successful"
        $hasMcpExe = $true
    } finally { Pop-Location }
}

# Verify required files
if (-not (Test-Path $mcpExe)) {
    Write-Err "Executable not found. Run without -NoBuild to compile."
    exit 1
}

# Create install directory
Write-Info "Install directory: $InstallPath"
if (-not (Test-Path $InstallPath)) {
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
}

# Stop running process if exists
$runningProcess = Get-Process -Name "windsurf-cunzhi" -ErrorAction SilentlyContinue
if ($runningProcess) {
    Write-Warn "windsurf-cunzhi.exe is running, stopping it..."
    $runningProcess | Stop-Process -Force
    Start-Sleep -Milliseconds 500
    Write-Ok "Process stopped"
}

# Copy files
Write-Info "Copying files..."
Copy-Item $mcpExe "$InstallPath\" -Force
Write-Ok "Copied windsurf-cunzhi.exe"

# Add to PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$InstallPath*") {
    Write-Info "Adding to user PATH..."
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallPath", "User")
    Write-Ok "Added to PATH (restart terminal to take effect)"
} else {
    Write-Info "Already in PATH"
}

# ============================================
# No MCP configuration needed (using run_command mode)
# ============================================
Write-Info "Skipping MCP configuration (using run_command mode)"
$windsurfConfigDir = "$env:USERPROFILE\.codeium\windsurf"

# ============================================
# Configure global rules (run_command mode)
# ============================================
$globalRulesDir = "$env:USERPROFILE\.codeium\windsurf\memories"
$globalRulesPath = "$globalRulesDir\global_rules.md"
$guiCommand = "$InstallPath\windsurf-cunzhi.exe"

Write-Info "Configuring global rules..."

# Ensure directory exists
if (-not (Test-Path $globalRulesDir)) {
    New-Item -ItemType Directory -Path $globalRulesDir -Force | Out-Null
}

# Rule content with run_command mode
$oldRuleMarkers = @("PRIORITY RULE - confirm", "PRIORITY RULE - zhi", "PRIORITY RULE - prompt", "PRIORITY RULE - pro", "Filesystem User Input", "PRIORITY RULE - read_user_input")
$zhiRuleMarker = "PRIORITY RULE - windsurf-input"
$zhiRuleContent = @"
# PRIORITY RULE - windsurf-input (MANDATORY)

**You MUST run ``windsurf-input`` command at the end of every response!**

Rules:
- Always run: ``$guiCommand --ui`` using run_command tool with Blocking=true
- You can pass custom options: ``--options "Option1,Option2,Option3"``
- You can pass custom message: ``--message "Your message here"``
- You can pass workspace for @file: ``--workspace "path/to/workspace"``
- Example: ``windsurf-cunzhi.exe --ui --message "Please choose" --options "Continue,Stop,Retry"``
- Always run this command before ending any response
- Never end a response without running this command
- Wait for user input from the command output

If command fails, inform user to reinstall windsurf-input.

---
"@

# Check and update global rules
$rulesUpdated = $false
if (Test-Path $globalRulesPath) {
    $existingRules = Get-Content $globalRulesPath -Raw -Encoding UTF8
    
    # Remove old rules
    foreach ($oldMarker in $oldRuleMarkers) {
        if ($existingRules -like "*$oldMarker*") {
            $lines = $existingRules -split "`r?`n"
            $newLines = @()
            $skipUntilDivider = $false
            foreach ($line in $lines) {
                if ($line -like "*$oldMarker*") {
                    $skipUntilDivider = $true
                    continue
                }
                if ($skipUntilDivider) {
                    if ($line -match "^---") {
                        $skipUntilDivider = $false
                    }
                    continue
                }
                $newLines += $line
            }
            $existingRules = ($newLines -join "`n").TrimStart()
            Write-Info "Removed old rule: $oldMarker"
        }
    }
    
    if ($existingRules -notlike "*$zhiRuleMarker*") {
        ($zhiRuleContent + "`n`n" + $existingRules) | Set-Content $globalRulesPath -Encoding UTF8
        Write-Ok "Added windsurf-input rule to global_rules.md"
    } else {
        # Save cleaned rules
        $existingRules | Set-Content $globalRulesPath -Encoding UTF8
        Write-Info "windsurf-input rule already exists in global_rules.md"
    }
} else {
    $defaultRules = @"
$zhiRuleContent

# Role: Software Development Assistant
- Follow best practices
- Ask for clarification when requirements are unclear
"@
    $defaultRules | Set-Content $globalRulesPath -Encoding UTF8
    Write-Ok "Created global_rules.md with windsurf-input rule"
}

# ============================================
# Installation complete
# ============================================
Write-Host ""
Write-Host "===============================================================" -ForegroundColor Green
Write-Ok "Installation complete!"
Write-Host "===============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installed files:" -ForegroundColor Yellow
Write-Host "  - windsurf-cunzhi.exe (GUI)" -ForegroundColor White
Write-Host "    Path: $InstallPath\windsurf-cunzhi.exe" -ForegroundColor Gray
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  - Global rules:  $globalRulesPath" -ForegroundColor White
Write-Host ""
Write-Host "Usage (via run_command):" -ForegroundColor Yellow
Write-Host "  windsurf-cunzhi.exe --ui                    - Basic GUI" -ForegroundColor White
Write-Host '  windsurf-cunzhi.exe --ui --options "A,B,C"  - With options' -ForegroundColor White
Write-Host '  windsurf-cunzhi.exe --ui --message "msg"    - With message' -ForegroundColor White
Write-Host ""
Write-Warn "Please restart Windsurf to apply changes!"
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
