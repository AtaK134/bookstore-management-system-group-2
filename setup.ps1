# Bookstore veritabanini kurar:
#   1) .env'deki kullanici ve veritabanini olusturur (postgres sifresi sorulur)
#   2) schema.sql ve data.sql'i bu kullanici ile calistirir
# Calistirma:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
if (-not (Test-Path $psql)) { $psql = 'psql' }

# .env oku
$envVars = @{}
Get-Content .env | Where-Object { $_ -match '^\s*([^#=]+?)\s*=\s*(.*)$' } | ForEach-Object {
    $envVars[$Matches[1]] = $Matches[2].Trim()
}
$dbHost = $envVars['DB_HOST']; $dbPort = $envVars['DB_PORT']
$dbName = $envVars['DB_NAME']; $dbUser = $envVars['DB_USER']; $dbPass = $envVars['DB_PASSWORD']

$env:PGCLIENTENCODING = 'UTF8'

Write-Host "1/3 Kullanici ve veritabani olusturuluyor (postgres sifresi istenecek)..."
& $psql -h $dbHost -p $dbPort -U postgres -d postgres -v ON_ERROR_STOP=1 `
    -v "db_name=$dbName" -v "db_user=$dbUser" -v "db_password=$dbPass" -f create_db.sql
if ($LASTEXITCODE -ne 0) { throw "Veritabani olusturulamadi." }

$env:PGPASSWORD = $dbPass
Write-Host "2/3 schema.sql calistiriliyor..."
& $psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -q -f schema.sql
if ($LASTEXITCODE -ne 0) { throw "schema.sql hata verdi." }

Write-Host "3/3 data.sql calistiriliyor..."
& $psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -q -f data.sql
if ($LASTEXITCODE -ne 0) { throw "data.sql hata verdi." }
Remove-Item Env:PGPASSWORD

Write-Host "Kurulum tamamlandi. DBeaver bilgileri .env dosyasinda."
