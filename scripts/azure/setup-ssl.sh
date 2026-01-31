#!/bin/bash
# =============================================================================
# setup-ssl.sh - Configurar SSL con Let's Encrypt
# 
# Uso:
#   ./scripts/azure/setup-ssl.sh isyourfinance.com admin@isyourfinance.com
# =============================================================================

set -e

DOMAIN="${1:-isyourfinance.com}"
EMAIL="${2:-admin@isyourfinance.com}"

echo "=============================================="
echo "  Configurando SSL para $DOMAIN"
echo "=============================================="

# -----------------------------------------------------------------------------
# 1. Verificar que certbot está instalado
# -----------------------------------------------------------------------------
if ! command -v certbot &> /dev/null; then
    echo "Instalando certbot..."
    sudo apt update && sudo apt install -y certbot
fi

# -----------------------------------------------------------------------------
# 2. Detener nginx si está corriendo
# -----------------------------------------------------------------------------
echo ""
echo "🔄 Deteniendo nginx temporalmente..."
cd /opt/finanzas
docker-compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true

# -----------------------------------------------------------------------------
# 3. Obtener certificado
# -----------------------------------------------------------------------------
echo ""
echo "🔐 Obteniendo certificado SSL..."
sudo certbot certonly --standalone \
    -d $DOMAIN \
    --email $EMAIL \
    --agree-tos \
    --non-interactive

# -----------------------------------------------------------------------------
# 4. Configurar renovación automática
# -----------------------------------------------------------------------------
echo ""
echo "⏰ Configurando renovación automática..."

# Crear script de renovación
cat << 'EOF' | sudo tee /opt/finanzas/renew-ssl.sh > /dev/null
#!/bin/bash
cd /opt/finanzas
docker-compose -f docker-compose.prod.yml stop nginx
certbot renew --quiet
docker-compose -f docker-compose.prod.yml start nginx
EOF

sudo chmod +x /opt/finanzas/renew-ssl.sh

# Agregar cron job para renovación (1ro de cada mes a las 3am)
CRON_CMD="0 3 1 * * /opt/finanzas/renew-ssl.sh >> /var/log/certbot-renew.log 2>&1"
(crontab -l 2>/dev/null | grep -v "renew-ssl.sh"; echo "$CRON_CMD") | crontab -

# -----------------------------------------------------------------------------
# 5. Reiniciar nginx
# -----------------------------------------------------------------------------
echo ""
echo "🚀 Reiniciando nginx..."
docker-compose -f docker-compose.prod.yml up -d nginx

# -----------------------------------------------------------------------------
# Verificar
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  ✅ SSL configurado para $DOMAIN"
echo "=============================================="
echo ""
echo "Verificando certificado..."
sudo certbot certificates

echo ""
echo "Prueba accediendo a: https://$DOMAIN/health"
echo ""

