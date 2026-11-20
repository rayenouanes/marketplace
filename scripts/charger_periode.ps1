# =====================================================================
# charger_periode.ps1 : charge plusieurs jours de données d'un coup
# (ingestion de Cris + transformations SQL de Lydia), pour les dashboards.
#
# Utilisation, depuis la racine du projet, dans PowerShell :
#   .\scripts\charger_periode.ps1 -Debut 2026-04-01 -Fin 2026-04-30
#
# Prérequis : postgres-dwh, minio, minio-init et api-marketplace allumés :
#   docker compose up -d postgres-dwh minio minio-init api-marketplace
# =====================================================================

param(
    [string]$Debut = "2026-04-01",
    [string]$Fin   = "2026-04-30"
)

$ErrorActionPreference = "Stop"

# 1. Liste des dates à charger
$dates = @()
$jour = [datetime]::ParseExact($Debut, "yyyy-MM-dd", $null)
$dernier = [datetime]::ParseExact($Fin, "yyyy-MM-dd", $null)
while ($jour -le $dernier) {
    $dates += $jour.ToString("yyyy-MM-dd")
    $jour = $jour.AddDays(1)
}
Write-Host "Dates à charger : $($dates.Count) jours, du $Debut au $Fin" -ForegroundColor Cyan

# 2. Ingestion de Cris pour toutes les dates, dans UN SEUL conteneur Airflow
#    (démarrer Airflow une seule fois est beaucoup plus rapide)
$listePython = ($dates | ForEach-Object { "'$_'" }) -join ","
$codePython = "from marketplace.run_ingestion import run_ingestion; [run_ingestion(d) for d in [$listePython]]"

Write-Host "`n=== Ingestion (API -> MinIO -> staging) ===" -ForegroundColor Cyan
docker compose run --rm --no-deps `
    -e CONNECTION_CHECK_MAX_COUNT=0 `
    -e _PIP_ADDITIONAL_REQUIREMENTS= `
    -w /opt/airflow/plugins `
    airflow-worker python -c $codePython
if ($LASTEXITCODE -ne 0) { throw "L'ingestion a échoué : arrêt du script." }

# 3. Transformations de Lydia, jour par jour, dans l'ordre
Write-Host "`n=== Transformations SQL (staging -> dwh -> analytics) ===" -ForegroundColor Cyan
$transform = Get-Content -Raw sql/transform_fact_orders.sql
$resume    = Get-Content -Raw sql/analytics_daily_summary.sql

foreach ($d in $dates) {
    ($transform -replace '\{\{\s*ds\s*\}\}', $d) |
        docker compose exec -T postgres-dwh psql -X -q -U marketplace -d marketplace -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "transform_fact_orders.sql a échoué pour $d" }

    ($resume -replace '\{\{\s*ds\s*\}\}', $d) |
        docker compose exec -T postgres-dwh psql -X -q -U marketplace -d marketplace -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw "analytics_daily_summary.sql a échoué pour $d" }

    Write-Host "  $d : OK"
}

# 4. Vérification
Write-Host "`n=== Résultat : analytics.daily_summary ===" -ForegroundColor Cyan
docker compose exec -T postgres-dwh psql -X -U marketplace -d marketplace -c "SELECT dt, total_orders, total_revenue, avg_basket FROM analytics.daily_summary WHERE dt BETWEEN '$Debut' AND '$Fin' ORDER BY dt;"