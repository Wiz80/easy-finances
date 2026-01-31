#!/bin/bash
# =============================================================================
# backup-to-github.sh - Backup encriptado a repositorio privado de GitHub
# 
# Prerequisitos:
#   1. Crear repo privado: github.com/TU_USUARIO/finanzas-backups
#   2. Configurar SSH key de deploy en la VM
#   3. Generar key GPG: gpg --full-generate-key
#   4. Exportar public key: gpg --export --armor TU_EMAIL > backup.pub
#
# Uso:
#   ./scripts/azure/backup-to-github.sh
#
# Programar con cron (diario a las 2am):
#   0 2 * * * /opt/finanzas/scripts/azure/backup-to-github.sh >> /var/log/finanzas-backup.log 2>&1
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------
BACKUP_REPO="${BACKUP_REPO:-git@github.com:TU_USUARIO/finanzas-backups.git}"
GPG_RECIPIENT="${GPG_RECIPIENT:-admin@isyourfinance.com}"
BACKUP_DIR="/tmp/finanzas-backup-$$"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=30

echo "=============================================="
echo "  Backup: $DATE"
echo "=============================================="

# -----------------------------------------------------------------------------
# 1. Crear directorio temporal
# -----------------------------------------------------------------------------
mkdir -p "$BACKUP_DIR"
trap "rm -rf $BACKUP_DIR" EXIT

# -----------------------------------------------------------------------------
# 2. Backup de PostgreSQL
# -----------------------------------------------------------------------------
echo ""
echo "📦 Haciendo backup de PostgreSQL..."
cd /opt/finanzas

docker-compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U "${POSTGRES_USER:-finanzas_user}" "${POSTGRES_DB:-finanzas_db}" \
    | gzip > "$BACKUP_DIR/postgres_$DATE.sql.gz"

echo "   Tamaño: $(du -h $BACKUP_DIR/postgres_$DATE.sql.gz | cut -f1)"

# -----------------------------------------------------------------------------
# 3. Encriptar con GPG
# -----------------------------------------------------------------------------
echo ""
echo "🔐 Encriptando backup..."
gpg --encrypt --recipient "$GPG_RECIPIENT" "$BACKUP_DIR/postgres_$DATE.sql.gz"
rm "$BACKUP_DIR/postgres_$DATE.sql.gz"

# -----------------------------------------------------------------------------
# 4. Subir a GitHub
# -----------------------------------------------------------------------------
echo ""
echo "📤 Subiendo a GitHub..."

# Clonar repo de backups
REPO_DIR="/tmp/finanzas-backups-$$"
git clone --depth 1 "$BACKUP_REPO" "$REPO_DIR" 2>/dev/null || {
    echo "❌ Error clonando repositorio de backups"
    echo "   Verifica que el repo existe y tienes acceso SSH"
    exit 1
}

# Copiar backup
cp "$BACKUP_DIR"/*.gpg "$REPO_DIR/"

# Limpiar backups viejos (mantener últimos N días)
cd "$REPO_DIR"
find . -name "*.gpg" -mtime +$KEEP_DAYS -delete 2>/dev/null || true

# Commit y push
git add .
git commit -m "Backup $DATE" || echo "Sin cambios para commit"
git push

# Cleanup
rm -rf "$REPO_DIR"

# -----------------------------------------------------------------------------
# Resumen
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  ✅ Backup completado: $DATE"
echo "=============================================="
echo ""
echo "Para restaurar:"
echo "  1. git clone $BACKUP_REPO"
echo "  2. gpg --decrypt postgres_$DATE.sql.gz.gpg > backup.sql.gz"
echo "  3. gunzip backup.sql.gz"
echo "  4. docker-compose exec -T postgres psql -U \$POSTGRES_USER \$POSTGRES_DB < backup.sql"
echo ""

