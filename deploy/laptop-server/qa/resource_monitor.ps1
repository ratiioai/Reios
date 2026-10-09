# Samples CPU (% of whole machine) and memory per component every 2 s until qa\STOP_RESOURCES exists.
param([string]$Out = "C:\reios-server\qa\results\resources.csv")
$cores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
$groups = @{ "api" = "python"; "postgres" = "postgres"; "nginx" = "nginx"; "tunnel" = "cloudflared" }
$apiPids = @{}
foreach ($line in (Get-Content C:\reios-server\logs\pids.txt | Where-Object { $_ -like "api:*" })) { $apiPids[[int]($line -split ":")[2]] = $true }
if (-not (Test-Path $Out)) { "time,component,cpu_pct,mem_mb" | Set-Content $Out }
$prev = @{}; $prevT = Get-Date
while (-not (Test-Path C:\reios-server\qa\STOP_RESOURCES)) {
    Start-Sleep -Seconds 2
    $now = Get-Date; $dt = ($now - $prevT).TotalSeconds; $prevT = $now
    $rows = @()
    foreach ($g in $groups.Keys) {
        $procs = Get-Process -Name $groups[$g] -ErrorAction SilentlyContinue
        if ($g -eq "api") {   # only the server's API instances, not test tools
            $apiPids = @{}; foreach ($line in (Get-Content C:\reios-server\logs\pids.txt | Where-Object { $_ -like "api:*" })) { $apiPids[[int]($line -split ":")[2]] = $true }
            # recorded pids are venv launchers; the real interpreter is their child process
            foreach ($cp in (Get-CimInstance Win32_Process -Filter "Name = 'python.exe'")) {
                if ($apiPids.ContainsKey([int]$cp.ParentProcessId)) { $apiPids[[int]$cp.ProcessId] = $true } }
            $procs = $procs | Where-Object { $apiPids.ContainsKey($_.Id) }
        }
        $cpu = 0; $mem = 0
        foreach ($p in $procs) {
            $t = $p.TotalProcessorTime.TotalSeconds; $key = "$g-$($p.Id)"
            if ($prev.ContainsKey($key)) { $cpu += ($t - $prev[$key]) }
            $prev[$key] = $t; $mem += $p.WorkingSet64
        }
        $rows += "{0},{1},{2:N1},{3:N0}" -f $now.ToString("HH:mm:ss"), $g, (100 * $cpu / $dt / $cores), ($mem / 1MB)
    }
    $total = (Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction SilentlyContinue).CounterSamples[0].CookedValue
    $rows += "{0},machine,{1:N1},{2:N0}" -f $now.ToString("HH:mm:ss"), $total, ((Get-CimInstance Win32_OperatingSystem | ForEach-Object { ($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / 1KB }))
    Add-Content $Out ($rows -replace ",(\d+),(\d+)", ',$1$2')
}
