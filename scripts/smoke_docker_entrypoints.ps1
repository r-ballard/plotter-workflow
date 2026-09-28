#requires -Version 5.1
<#
.SYNOPSIS
    Host-runnable smoke test for the dpx3300-plotter:local Docker image.

.DESCRIPTION
    Inspects the image, then invokes its ENTRYPOINT (uv run --no-sync python)
    with --help for the non-hardware scripts: dpx3300_convert.py,
    cootie_impose.py, job_preflight.py. Runs each with --network none.
    Never runs send_hpgl.py, mounts paths, passes a serial device, or
    transmits HP-GL. Exits nonzero if any check fails.
#>
[CmdletBinding()]
param(
    [string]$Image = "dpx3300-plotter:local"
)

$ErrorActionPreference = "Stop"

$scripts = @("dpx3300_convert.py", "cootie_impose.py", "job_preflight.py")

function Invoke-SmokeScript {
    param([string]$ScriptName)

    Write-Host "== $ScriptName =="
    docker run --rm --network none $Image $ScriptName "--help"
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host "PASS: $ScriptName (exit 0)"
    } else {
        Write-Host "FAIL: $ScriptName (exit $code)"
    }
    return $code
}

try {
    docker image inspect $Image 1>$null 2>$null
    $inspectCode = $LASTEXITCODE
} catch {
    $inspectCode = 1
}
if ($inspectCode -ne 0) {
    Write-Host "FAIL: Image '$Image' is unavailable. Build it with 'docker compose build converter' or check Docker Desktop."
    exit 1
}
Write-Host "Image '$Image' present."

$failures = 0
foreach ($s in $scripts) {
    $code = Invoke-SmokeScript -ScriptName $s
    if ($code -ne 0) {
        $failures++
    }
}

if ($failures -gt 0) {
    Write-Host "Smoke failed: $failures of $($scripts.Count) scripts."
    exit 1
}
Write-Host "Smoke passed: all $($scripts.Count) scripts."
exit 0
