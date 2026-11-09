param(
    [string]$SourceDirectory = 'voting-system',
    [string]$OutputDirectory = 'artifacts'
)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
$output = (New-Item -ItemType Directory -Path $OutputDirectory -Force).FullName
$work = (New-Item -ItemType Directory -Path (Join-Path ([IO.Path]::GetTempPath()) ('votelab-' + [Guid]::NewGuid().ToString('N')))).FullName
$package = New-Item -ItemType Directory -Path (Join-Path $work 'package')
$runtime = New-Item -ItemType Directory -Path (Join-Path $package.FullName 'runtime')
$appDirectory = New-Item -ItemType Directory -Path (Join-Path $package.FullName 'app')

function Get-VerifiedArchive($Url, $Path, $ExpectedHash) {
    Invoke-WebRequest -Uri $Url -OutFile $Path
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $ExpectedHash) {
        throw "SHA-256 mismatch for $Url"
    }
}

$pythonUrl = 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip'
$pythonHash = '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38'
$pythonArchive = Join-Path $work 'python.zip'
Get-VerifiedArchive $pythonUrl $pythonArchive $pythonHash
Expand-Archive -LiteralPath $pythonArchive -DestinationPath $runtime.FullName

$pillowMetadata = Invoke-RestMethod 'https://pypi.org/pypi/Pillow/12.3.0/json'
$pillow = $pillowMetadata.urls | Where-Object { $_.filename -eq 'pillow-12.3.0-cp313-cp313-win_amd64.whl' }
$pillowHash = '1cca606cd25738df4ed873d5ad46bbdb3d83b5cbca291f6b4ff13a4df6b0bbe8'
$wheel = Join-Path $work 'pillow.zip'
Get-VerifiedArchive $pillow.url $wheel $pillowHash
$sitePackages = Join-Path $runtime.FullName 'Lib/site-packages'
Expand-Archive -LiteralPath $wheel -DestinationPath $sitePackages
Set-Content -LiteralPath (Join-Path $runtime.FullName 'python313._pth') -Value @('python313.zip', '.', 'Lib\site-packages', '..\app') -Encoding ASCII
@"
CPython 3.13.17 Windows embedded distribution
$pythonUrl
SHA-256 $pythonHash
License LICENSE.txt

Pillow 12.3.0 Windows wheel
$($pillow.url)
SHA-256 $pillowHash
License Lib/site-packages/pillow-12.3.0.dist-info/licenses/LICENSE
"@ | Set-Content -LiteralPath (Join-Path $runtime.FullName 'RUNTIME-PROVENANCE.txt') -Encoding UTF8

$appFiles = @('app.py', 'auth.py', 'demo_server.py', 'entries.py', 'lifecycle.py', 'maintenance.py', 'schema.sql', 'ui3.py', 'ui4.py', 'voting_rules.py', 'web3.py', 'web4.py', 'run_votelab.py')
foreach ($name in $appFiles) { Copy-Item -LiteralPath (Join-Path $source $name) -Destination $appDirectory.FullName }
Copy-Item -LiteralPath (Join-Path $source 'static') -Destination $appDirectory.FullName -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Start VoteLab.bat') -Destination $package.FullName
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'READ ME FIRST.txt') -Destination $package.FullName

$archive = Join-Path $output 'VoteLab-0.4.2-Windows-x64.zip'
Compress-Archive -Path (Join-Path $package.FullName '*') -DestinationPath $archive -CompressionLevel Optimal
$extracted = Join-Path $work 'Extracted VoteLab'
Expand-Archive -LiteralPath $archive -DestinationPath $extracted
$python = Join-Path $extracted 'runtime/python.exe'
$launcher = Join-Path $extracted 'app/run_votelab.py'
$env:VOTELAB_DATA_DIR = Join-Path $work 'data'
$fixture = Join-Path $work 'fixture.json'
$smoke = Join-Path $source 'tools/http_persistence_smoke.py'
foreach ($phase in @('before', 'after')) {
    $stdout = Join-Path $work "$phase.out"
    $stderr = Join-Path $work "$phase.err"
    $server = Start-Process -FilePath $python -ArgumentList @('-B', ('"' + $launcher + '"'), '--no-browser', '--port', '0') -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    try {
        $address = $null
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if ($server.HasExited) { break }
            Start-Sleep -Milliseconds 300
            if ((Get-Content -LiteralPath $stdout -Raw) -match 'ready at (http://127\.0\.0\.1:\d+)/') {
                $address = $Matches[1]
                break
            }
        }
        if (!$address) { throw "VoteLab failed to start. $(Get-Content -LiteralPath $stderr -Raw)" }
        & $python -B $smoke $phase $address $fixture
        if ($LASTEXITCODE -ne 0) { throw "Windows archive failed the $phase persistence check." }
    } finally {
        if (!$server.HasExited) { Stop-Process -Id $server.Id }
        $server.WaitForExit()
    }
}
Get-FileHash -LiteralPath $archive -Algorithm SHA256
