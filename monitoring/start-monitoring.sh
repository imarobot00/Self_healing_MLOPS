#!/bin/bash
# ==============================================================================
# MLOps Monitoring Stack - Startup Script
# ==============================================================================
# This script starts the complete monitoring stack:
# - Prometheus (metrics collection)
# - Grafana (visualization)
# - Alert Manager (alert routing)
# - Node Exporter (system metrics)
# - cAdvisor (container metrics)
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}   MLOps Monitoring Stack - Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ====================
# Pre-flight Checks
# ====================
echo -e "${YELLOW}🔍 Running pre-flight checks...${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker daemon is not running. Please start Docker.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is installed and running${NC}"

# Check required files
REQUIRED_FILES=(
    "docker-compose.yml"
    "prometheus.yml"
    "alert_rules.yml"
    "alertmanager.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SCRIPT_DIR/$file" ]; then
        echo -e "${RED}❌ Missing required file: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required configuration files present${NC}"

# ====================
# Create Directories
# ====================
echo ""
echo -e "${YELLOW}📁 Creating directories...${NC}"

mkdir -p "$SCRIPT_DIR/grafana/provisioning/datasources"
mkdir -p "$SCRIPT_DIR/grafana/provisioning/dashboards"
mkdir -p "$SCRIPT_DIR/grafana/dashboards"

echo -e "${GREEN}✅ Directories created${NC}"

# ====================
# Stop Existing Containers
# ====================
echo ""
echo -e "${YELLOW}🛑 Stopping any existing monitoring containers...${NC}"

cd "$SCRIPT_DIR"
if docker compose version &> /dev/null; then
    docker compose down 2>/dev/null || true
else
    docker-compose down 2>/dev/null || true
fi

echo -e "${GREEN}✅ Existing containers stopped${NC}"

# ====================
# Start Monitoring Stack
# ====================
echo ""
echo -e "${YELLOW}🚀 Starting monitoring stack...${NC}"

if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

# ====================
# Wait for Services
# ====================
echo ""
echo -e "${YELLOW}⏳ Waiting for services to be healthy...${NC}"

# Function to wait for service
wait_for_service() {
    local name=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo -n "  Waiting for $name"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e " ${RED}✗ (timeout)${NC}"
    return 1
}

# Wait for each service
wait_for_service "Prometheus" "http://localhost:9090/-/healthy"
wait_for_service "Grafana" "http://localhost:3000/api/health"
wait_for_service "Alert Manager" "http://localhost:9093/-/healthy"
wait_for_service "Node Exporter" "http://localhost:9100/metrics"

# ====================
# Display Status
# ====================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Monitoring Stack Started Successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📊 Service URLs:${NC}"
echo -e "  ${YELLOW}Prometheus:${NC}    http://localhost:9090"
echo -e "  ${YELLOW}Grafana:${NC}       http://localhost:3000 (admin/admin)"
echo -e "  ${YELLOW}Alert Manager:${NC} http://localhost:9093"
echo -e "  ${YELLOW}Node Exporter:${NC} http://localhost:9100"
echo -e "  ${YELLOW}cAdvisor:${NC}      http://localhost:8080"
echo ""
echo -e "${BLUE}🎯 Quick Actions:${NC}"
echo -e "  ${YELLOW}View logs:${NC}     docker compose logs -f"
echo -e "  ${YELLOW}Stop stack:${NC}    docker compose down"
echo -e "  ${YELLOW}Restart:${NC}       docker compose restart"
echo -e "  ${YELLOW}Check status:${NC}  docker compose ps"
echo ""
echo -e "${BLUE}📈 Next Steps:${NC}"
echo -e "  1. Open Grafana: ${YELLOW}http://localhost:3000${NC}"
echo -e "  2. Login with ${YELLOW}admin/admin${NC}"
echo -e "  3. Go to Dashboards → MLOps folder"
echo -e "  4. View 'ML System Overview' dashboard"
echo ""
echo -e "${BLUE}🔔 To Configure Alerts:${NC}"
echo -e "  1. Edit ${YELLOW}alertmanager.yml${NC}"
echo -e "  2. Set your Slack webhook and email credentials"
echo -e "  3. Restart: ${YELLOW}docker compose restart alertmanager${NC}"
echo ""
echo -e "${GREEN}Happy Monitoring! 🎉${NC}"
echo ""
