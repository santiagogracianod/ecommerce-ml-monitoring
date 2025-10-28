#!/bin/bash
# Script para iniciar el servicio de monitoreo

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Iniciando Monitoring Service...${NC}"

# Verificar que existe el entorno virtual
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Entorno virtual no encontrado. Ejecuta primero: ./init_monitoring.sh${NC}"
    exit 1
fi

# Activar entorno virtual
source venv/bin/activate

# Verificar que la base de datos existe
if [ ! -f "data/monitoring.db" ]; then
    echo -e "${YELLOW}⚠️  Base de datos no encontrada. Inicializando...${NC}"
    python3 -c "import asyncio; from src.storage.database import init_db; asyncio.run(init_db())"
fi

# Iniciar servicio
echo -e "${GREEN}✅ Iniciando servidor en http://0.0.0.0:8003${NC}"
echo -e "${GREEN}📊 Documentación en http://localhost:8003/api/v1/docs${NC}"
echo ""
python -m uvicorn src.main:app --host 0.0.0.0 --port 8003 --reload
