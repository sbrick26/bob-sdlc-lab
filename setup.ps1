# Bob SDLC lab setup for Windows (PowerShell 5.1 or 7). macOS and Linux: run ./setup.sh
# Run from the repo folder:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot
$DashboardUrl = if ($env:DASHBOARD_URL) { $env:DASHBOARD_URL } else { 'https://bob-sdlc-lab-dashboard.2fxmskmi3eal.ca-tor.codeengine.appdomain.cloud' }

function Ok($t)   { Write-Host "  ok       $t" }
function Miss($t) { Write-Host "  missing  $t" -ForegroundColor Yellow }
function Has($c)  { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

Write-Host "1. Checking what the lab needs"
$needs = @()
if (Has git)    { Ok 'git' }    else { Miss 'git';    $needs += 'Git.Git' }
# Find a real Python 3.10+: skip the Microsoft Store placeholder (WindowsApps) and launchers that answer nothing.
function Find-Python {
  $cands = @()
  foreach ($n in @('python','python3')) {
    Get-Command $n -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -and $_.Source -notmatch 'WindowsApps' } | ForEach-Object { $cands += ,@($_.Source) }
  }
  if (Get-Command py -ErrorAction SilentlyContinue) { $cands += ,@('py','-3') }
  foreach ($c in $cands) {
    $exe = $c[0]; $rest = @(); if ($c.Count -gt 1) { $rest = $c[1..($c.Count - 1)] }
    try { $out = & $exe @rest -c 'import sys;print(sys.executable if sys.version_info>=(3,10) else str())' 2>$null } catch { $out = $null }
    $line = @($out | Where-Object { $_ -and $_.Trim() }) | Select-Object -First 1
    if ($line -and (Test-Path $line.Trim())) { return $line.Trim() }
  }
  return $null
}
$pyExe = Find-Python
if (-not $pyExe) { Get-Command python,python3,py -All -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    seen: $($_.Source)" } }
if ($pyExe) { Ok "python ($pyExe)" } else { Miss 'python 3.10+'; $needs += 'Python.Python.3.12' }
if ($needs.Count -gt 0) {
  if (Has winget) {
    $a = Read-Host "Install $($needs -join ', ') with winget now? [y/N]"
    if ($a -match '^[yY]') {
      foreach ($n in $needs) { winget install --id $n -e --accept-source-agreements --accept-package-agreements }
      Write-Host "Installed. Close this window, open a new PowerShell, and run setup.ps1 again so the new tools are on PATH."
      exit 0
    }
  }
  Write-Host "Install $($needs -join ', ') (winget or the vendor sites), then run setup.ps1 again."; exit 1
}
# Bob's hooks run "python3 ...". Windows Python seldom provides python3, so add a small shim on the user PATH.
$shimDir = Join-Path $env:USERPROFILE '.bob-lab\bin'
New-Item -ItemType Directory -Force -Path $shimDir | Out-Null
Set-Content -Path (Join-Path $shimDir 'python3.cmd') -Value "@echo off`r`n`"$pyExe`" %*" -Encoding ASCII
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not ($userPath -split ';' | Where-Object { $_ -eq $shimDir })) {
  [Environment]::SetEnvironmentVariable('Path', "$shimDir;$userPath", 'User')
  $env:Path = "$shimDir;$env:Path"
  Ok 'python3 shortcut for Bob hooks (restart Bob IDE if it is open)'
} else { Ok 'python3 shortcut for Bob hooks' }

$bobExe = @("$env:LOCALAPPDATA\Programs\IBM Bob\IBM Bob.exe", "$env:ProgramFiles\IBM Bob\IBM Bob.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($bobExe) { Ok 'IBM Bob IDE' } else { Miss 'IBM Bob IDE (install from https://bob.ibm.com and sign in once; setup continues)' }

Write-Host ""
Write-Host "2. Who are you?"
$cur = @{}
if (Test-Path 'lab.env') { Get-Content 'lab.env' | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.*)$') { $cur[$Matches[1]] = $Matches[2] } } }
$curN = $null
if ($cur['LAB_USER']) { $curN = @{ 'sam'='1'; 'priya'='2'; 'jordan'='3'; 'alex'='4' }[$cur['LAB_USER']] }
if ($curN) { Write-Host "   Current profile: $curN" }
Write-Host "   Pick your lab profile from your card:"
Write-Host "     1) Sam Lab      Platform"
Write-Host "     2) Priya Lab    Platform"
Write-Host "     3) Jordan Lab   Field Apps"
Write-Host "     4) Alex Lab     Field Apps"
$profiles = @{ '1' = @('sam','KAN-157'); '2' = @('priya','KAN-158'); '3' = @('jordan','KAN-159'); '4' = @('alex','KAN-160') }
if ($env:LAB_PROFILE -and $profiles.ContainsKey($env:LAB_PROFILE)) { $choice = $env:LAB_PROFILE } else {
do {
  $prompt = if ($curN) { "   Enter 1-4, or press Enter to keep $curN" } else { '   Enter 1-4' }
  $choice = Read-Host $prompt
  if (-not $choice -and $curN) { $choice = $curN }
} until ($profiles.ContainsKey($choice))
}
$Name = $profiles[$choice][0]; $Ticket = $profiles[$choice][1]
$Full = ($Name.Substring(0,1).ToUpper() + $Name.Substring(1)) + ' Lab'

if ($env:DASHBOARD_TOKEN) { $DashToken = $env:DASHBOARD_TOKEN } else {
  $hint = if ($cur['DASHBOARD_TOKEN']) { ' (saved; press Enter to keep)' } else { '' }
  $DashToken = Read-Host "   Dashboard token from your card$hint"
  if (-not $DashToken) { $DashToken = $cur['DASHBOARD_TOKEN'] }
}
if ($env:LAB_GH_TOKEN) { $GhToken = $env:LAB_GH_TOKEN } else {
  $hint = if ($cur['LAB_GH_TOKEN']) { ' (saved; press Enter to keep)' } else { '' }
  $sec = Read-Host "   GitHub lab token from your card$hint, hidden as you type" -AsSecureString
  $GhToken = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
  if (-not $GhToken) { $GhToken = $cur['LAB_GH_TOKEN'] }
}
if (-not $DashToken -or -not $GhToken) { Write-Host 'Both tokens from your card are needed. Run setup.ps1 again.'; exit 1 }
@(
  "LAB_USER=$Name", 'LAB_ROLE=participant', 'LAB_TEAM=',
  "DASHBOARD_URL=$DashboardUrl", "DASHBOARD_TOKEN=$DashToken", "LAB_GH_TOKEN=$GhToken"
) | Set-Content -Path 'lab.env' -Encoding ASCII
$Team = @{ 'sam'='Platform'; 'priya'='Platform'; 'jordan'='Field Apps'; 'alex'='Field Apps' }[$Name]
@(
  "user=$Name", "name=$Full", "team=$Team", "ticket=$Ticket",
  "jira_ticket=https://demo-ibm-bob.atlassian.net/browse/$Ticket",
  'jira_board=https://demo-ibm-bob.atlassian.net/jira/software/projects/KAN/boards',
  "prs=https://github.com/sbrick26/bob-sdlc-lab/pulls?q=is%3Apr+label%3A$Name",
  "dashboard=$DashboardUrl/#/audit?user=$Name"
) | Set-Content -Path 'my-lab.txt' -Encoding ASCII
git config user.name "$Full"
git config user.email "$Name@lab.sequoia.example"
# Push as the shared lab account, for this folder only. Git for Windows runs this helper with its bundled sh.
git config credential.https://github.com.helper ""
# Windows PowerShell 5.1 strips embedded double quotes from native arguments, so keep the helper logic in a file.
$gitDir = (Resolve-Path (git rev-parse --git-dir)).Path -replace '\\','/'
$helper = "$gitDir/lab-credential.sh"
[IO.File]::WriteAllText($helper, "#!/bin/sh`nroot=`"`$(git rev-parse --show-toplevel)`"`necho username=x-access-token`necho `"password=`$(sed -n 's/^LAB_GH_TOKEN=//p' `"`$root/lab.env`")`"`n")
git config --add credential.https://github.com.helper "!sh '$helper'"
git fetch -q origin demo-dev 2>$null

Write-Host ""
Write-Host "3. Setting up the app"
if (-not (Test-Path '.venv')) { & $pyExe -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -q --disable-pip-version-check -r requirements.txt pytest
Ok 'FieldOps app and tests'
try { $r = Invoke-WebRequest -Uri "$DashboardUrl/healthz" -UseBasicParsing -TimeoutSec 8; Ok 'Lab dashboard reachable' }
catch { Miss 'Lab dashboard not reachable; tell the facilitator. The lab still works.' }

Write-Host ""
Write-Host "Ready, $Full. Your details:"
Write-Host "  Ticket        $Ticket"
Write-Host "  Jira          https://demo-ibm-bob.atlassian.net/jira/software/projects/KAN/boards"
Write-Host "  Jira login    ibm.demo.dev+$Name@gmail.com, password from your card"
Write-Host "  Dashboard     $DashboardUrl"
Write-Host "  Pull requests https://github.com/sbrick26/bob-sdlc-lab/pulls?q=is%3Apr+label%3A$Name"
Write-Host "  Lab guide     https://github.com/sbrick26/bob-sdlc-lab/blob/main/docs/participant-guide.md"
Write-Host ""
Write-Host "Next: in Bob IDE pick the SDLC mode and type: check my tickets"
Write-Host "The first Jira call opens a browser: sign in with your Jira login above."
if ($bobExe) { Start-Process -FilePath $bobExe -ArgumentList "`"$PWD`"" }
