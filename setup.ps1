# Optional: installs the bookstore database into a LOCAL PostgreSQL (without Docker).
#   1) creates the user and database from .env (asks for the postgres password)
#   2) runs schema.sql and data.sql as that user
# Usage:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
if (-not (Test-Path $psql)) { $psql = 'psql' }

# Read .env (falls back to the same defaults as docker-compose.yml)
$envVars = @{ DB_HOST = 'localhost'; DB_PORT = '5432'; DB_NAME = 'bookstore'; DB_USER = 'bookstore_user'; DB_PASSWORD = 'bookstore_pass' }
if (Test-Path .env) {
    Get-Content .env | Where-Object { $_ -match '^\s*([^#=]+?)\s*=\s*(.*)$' } | ForEach-Object {
        $envVars[$Matches[1]] = $Matches[2].Trim()
    }
}
$dbHost = $envVars['DB_HOST']; $dbPort = $envVars['DB_PORT']
$dbName = $envVars['DB_NAME']; $dbUser = $envVars['DB_USER']; $dbPass = $envVars['DB_PASSWORD']

$env:PGCLIENTENCODING = 'UTF8'

Write-Host "1/3 Creating user and database (the postgres password will be asked)..."
& $psql -h $dbHost -p $dbPort -U postgres -d postgres -v ON_ERROR_STOP=1 `
    -v "db_name=$dbName" -v "db_user=$dbUser" -v "db_password=$dbPass" -f create_db.sql
if ($LASTEXITCODE -ne 0) { throw "Could not create the database." }

$env:PGPASSWORD = $dbPass
Write-Host "2/3 Running schema.sql..."
& $psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -q -f schema.sql
if ($LASTEXITCODE -ne 0) { throw "schema.sql failed." }

Write-Host "3/3 Running data.sql..."
& $psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -q -f data.sql
if ($LASTEXITCODE -ne 0) { throw "data.sql failed." }
Remove-Item Env:PGPASSWORD

Write-Host "Done. Connection details are in .env."
