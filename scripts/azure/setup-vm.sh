#!/bin/bash
# =============================================================================
# setup-vm.sh - Configuración inicial de Azure VM
# 
# Uso:
#   scp scripts/azure/setup-vm.sh finanzasadmin@<VM_IP>:~/
#   ssh finanzasadmin@<VM_IP>
#   chmod +x setup-vm.sh && ./setup-vm.sh
# =============================================================================

set -e

echo "=============================================="
echo "  Configurando VM para Finanzas MVP"
echo "=============================================="

# -----------------------------------------------------------------------------
# 1. Actualizar sistema
# -----------------------------------------------------------------------------
echo ""
echo "📦 [1/6] Actualizando sistema..."
sudo apt update && sudo apt upgrade -y

# -----------------------------------------------------------------------------
# 2. Instalar Docker
# -----------------------------------------------------------------------------
echo ""
echo "🐳 [2/6] Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "✅ Docker instalado. Necesitarás cerrar sesión y volver a entrar."
else
    echo "✅ Docker ya está instalado."
fi

# -----------------------------------------------------------------------------
# 3. Instalar Docker Compose
# -----------------------------------------------------------------------------
echo ""
echo "🐳 [3/6] Instalando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose instalado."
else
    echo "✅ Docker Compose ya está instalado."
fi

# Verificar versiones
docker --version
docker-compose --version

# -----------------------------------------------------------------------------
# 4. Montar disco de datos (si existe /dev/sdc)
# -----------------------------------------------------------------------------
echo ""
echo "💾 [4/6] Configurando disco de datos..."
if [ -b /dev/sdc ]; then
    # Verificar si ya está montado
    if mountpoint -q /mnt/data; then
        echo "✅ Disco de datos ya está montado en /mnt/data"
    else
        # Formatear si es necesario (CUIDADO: esto borra datos)
        if ! blkid /dev/sdc; then
            echo "Formateando disco /dev/sdc..."
            sudo mkfs.ext4 /dev/sdc
        fi
        
        # Crear punto de montaje
        sudo mkdir -p /mnt/data
        
        # Montar
        sudo mount /dev/sdc /mnt/data
        
        # Agregar a fstab para montaje automático
        if ! grep -q "/dev/sdc" /etc/fstab; then
            echo '/dev/sdc /mnt/data ext4 defaults 0 2' | sudo tee -a /etc/fstab
        fi
        
        echo "✅ Disco de datos montado en /mnt/data"
    fi
else
    echo "⚠️  No se encontró disco de datos en /dev/sdc"
    echo "   Usando /mnt/data local..."
    sudo mkdir -p /mnt/data
fi

# Crear directorios para datos
sudo mkdir -p /mnt/data/postgres
sudo mkdir -p /mnt/data/redis
sudo chown -R $USER:$USER /mnt/data

# -----------------------------------------------------------------------------
# 5. Crear directorio de aplicación
# -----------------------------------------------------------------------------
echo ""
echo "📁 [5/6] Creando directorio de aplicación..."
sudo mkdir -p /opt/finanzas
sudo chown -R $USER:$USER /opt/finanzas

# -----------------------------------------------------------------------------
# 6. Instalar herramientas útiles
# -----------------------------------------------------------------------------
echo ""
echo "🔧 [6/6] Instalando herramientas adicionales..."
sudo apt install -y \
    git \
    curl \
    htop \
    ncdu \
    certbot

# -----------------------------------------------------------------------------
# Resumen
# -----------------------------------------------------------------------------
echo ""
echo "=============================================="
echo "  ✅ Configuración completada"
echo "=============================================="
echo ""
echo "Próximos pasos:"
echo "  1. Cierra sesión y vuelve a entrar para aplicar grupo docker"
echo "  2. Clona el repositorio:"
echo "     git clone https://github.com/TU_USUARIO/finanzas_personales_inteligentes.git /opt/finanzas"
echo "  3. Configura las variables de entorno:"
echo "     cp /opt/finanzas/env.example /opt/finanzas/.env"
echo "     nano /opt/finanzas/.env"
echo "  4. Configura SSL:"
echo "     ./scripts/azure/setup-ssl.sh"
echo "  5. Levanta los servicios:"
echo "     cd /opt/finanzas && docker-compose -f docker-compose.prod.yml up -d"
echo ""

