Write-Host "Running database migration..." -ForegroundColor Cyan

$psqlPath = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$sqlFile = "C:\Users\palan\IdeaProjects\Can_ser\migration_update_schema.sql"

# Run the migration
& $psqlPath -U postgres -d canonical_db -f $sqlFile

Write-Host "`nMigration script executed!" -ForegroundColor Green
Write-Host "Check output above for any errors" -ForegroundColor Yellow
