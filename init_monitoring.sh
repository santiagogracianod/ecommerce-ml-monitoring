#!/bin/bash
# Script de inicialización del servicio de monitoreo ML

set -e

echo "🚀 Iniciando configuración del servicio de monitoreo ML..."

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 no está instalado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python encontrado: $(python3 --version)${NC}"

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creando entorno virtual...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Entorno virtual creado${NC}"
else
    echo -e "${GREEN}✅ Entorno virtual ya existe${NC}"
fi

# Activar entorno virtual
echo -e "${YELLOW}📦 Activando entorno virtual...${NC}"
source venv/bin/activate

# Instalar dependencias
echo -e "${YELLOW}📦 Instalando dependencias...${NC}"
pip install -r requirements.txt -q

echo -e "${GREEN}✅ Dependencias instaladas${NC}"

# Crear archivo .env si no existe
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚙️  Creando archivo .env desde .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Archivo .env creado${NC}"
else
    echo -e "${GREEN}✅ Archivo .env ya existe${NC}"
fi

# Crear directorios necesarios
echo -e "${YELLOW}📁 Creando directorios de datos...${NC}"
mkdir -p data/reference data/reports data/logs

echo -e "${GREEN}✅ Directorios creados${NC}"

# Inicializar base de datos
echo -e "${YELLOW}🗄️  Inicializando base de datos...${NC}"
python3 -c "import asyncio; from src.storage.database import init_db; asyncio.run(init_db())"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Base de datos inicializada correctamente${NC}"
else
    echo -e "${RED}❌ Error al inicializar la base de datos${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Configuración completada exitosamente!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Para iniciar el servicio, ejecuta:"
echo -e "${YELLOW}  source venv/bin/activate${NC}"
echo -e "${YELLOW}  python -m uvicorn src.main:app --host 0.0.0.0 --port 8003 --reload${NC}"
echo ""
echo -e "O simplemente:"
echo -e "${YELLOW}  ./start_monitoring.sh${NC}"
echo ""
echo -e "Documentación: ${YELLOW}http://localhost:8003/api/v1/docs${NC}"
echo ""
