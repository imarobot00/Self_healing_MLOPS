#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          🚀 Starting Self-Healing MLOps System - Docker Deployment          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if Docker is running
docker_running() {
    docker info >/dev/null 2>&1
}

# Function to wait for service to be healthy
wait_for_service() {
    local service_name=$1
    local max_attempts=${2:-30}
    local attempt=1
    
    echo -ne "${YELLOW}  Waiting for ${service_name}...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if $DOCKER_COMPOSE -f docker-compose.mlops.yml ps | grep -q "${service_name}.*healthy"; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    echo -e " ${RED}✗ (timeout)${NC}"
    return 1
}

# Pre-flight checks
echo -e "${BLUE}🔍 Running pre-flight checks...${NC}"

if ! command_exists docker; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check for docker compose (v2) or docker-compose (v1)
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command_exists docker-compose; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

if ! docker_running; then
    echo -e "${RED}❌ Docker daemon is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi

echo -e "${GREEN}✅ Docker is installed and running${NC}"

# Check if monitoring stack is running
echo -e "${BLUE}🔍 Checking monitoring stack...${NC}"
if ! docker network ls | grep -q "monitoring_monitoring"; then
    echo -e "${YELLOW}⚠️  Monitoring stack not running. Starting it first...${NC}"
    cd monitoring
    ./start-monitoring.sh
    cd ..
    echo -e "${GREEN}✅ Monitoring stack started${NC}"
else
    echo -e "${GREEN}✅ Monitoring stack is running${NC}"
fi

# Check required files
echo -e "${BLUE}🔍 Checking required files...${NC}"
required_files=(
    "api/Dockerfile"
    "training/Dockerfile"
    "docker-compose.mlops.yml"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Required file missing: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required files present${NC}"

# Stop existing MLOps containers
echo ""
echo -e "${BLUE}🛑 Stopping any existing MLOps containers...${NC}"
$DOCKER_COMPOSE -f docker-compose.mlops.yml down 2>/dev/null || true
echo -e "${GREEN}✅ Existing containers stopped${NC}"

# Build images
echo ""
echo -e "${BLUE}🔨 Building Docker images...${NC}"
echo -e "${YELLOW}This may take a few minutes on first run...${NC}"
$DOCKER_COMPOSE -f docker-compose.mlops.yml build --no-cache

echo -e "${GREEN}✅ Docker images built${NC}"

# Start services
echo ""
echo -e "${BLUE}🚀 Starting MLOps services...${NC}"
$DOCKER_COMPOSE -f docker-compose.mlops.yml up -d

echo -e "${GREEN}✅ Services started${NC}"

# Wait for services to be healthy
echo ""
echo -e "${BLUE}⏳ Waiting for services to be healthy...${NC}"
wait_for_service "mlops-training" 60
wait_for_service "mlops-api" 60
wait_for_service "mlops-orchestrator" 60

# Check Prometheus targets
echo ""
echo -e "${BLUE}🔍 Verifying Prometheus integration...${NC}"
sleep 5  # Give Prometheus time to scrape
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import sys, json
data = json.load(sys.stdin)
ml_services = ['mlops-api', 'mlops-training', 'mlops-orchestrator']
for target in data['data']['activeTargets']:
    job = target['scrapePool']
    if job in ml_services:
        health = target['health']
        status = '✅' if health == 'up' else '❌'
        print(f'  {status} {job:<25} {health}')
" 2>/dev/null || echo -e "${YELLOW}  ⚠️  Could not verify targets (Prometheus may still be starting)${NC}"

# Display service URLs and status
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                          🎉 Deployment Complete!                             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📊 ML Services:${NC}"
echo -e "  API:            http://localhost:8000"
echo -e "  API Docs:       http://localhost:8000/docs"
echo -e "  API Health:     http://localhost:8000/health"
echo -e "  API Metrics:    http://localhost:8000/metrics/prometheus"
echo -e "  Training:       http://localhost:8001"
echo -e "  Orchestrator:   http://localhost:8002"
echo ""
echo -e "${GREEN}📈 Monitoring:${NC}"
echo -e "  Grafana:        http://localhost:3000 (admin/admin)"
echo -e "  Prometheus:     http://localhost:9090"
echo -e "  Targets:        http://localhost:9090/targets"
echo -e "  Alerts:         http://localhost:9090/alerts"
echo -e "  Alert Manager:  http://localhost:9093"
echo ""
echo -e "${GREEN}⚡ Quick Actions:${NC}"
echo -e "  View logs:      $DOCKER_COMPOSE -f docker-compose.mlops.yml logs -f"
echo -e "  Stop services:  $DOCKER_COMPOSE -f docker-compose.mlops.yml down"
echo -e "  Restart:        $DOCKER_COMPOSE -f docker-compose.mlops.yml restart"
echo -e "  Status:         $DOCKER_COMPOSE -f docker-compose.mlops.yml ps"
echo ""
echo -e "${GREEN}🧪 Test the System:${NC}"
echo -e "  # Make a prediction"
echo -e "  curl -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{\"features\": {...}}'"
echo ""
echo -e "  # Check metrics"
echo -e "  curl http://localhost:8000/metrics/prometheus"
echo ""
echo -e "  # View Grafana dashboards"
echo -e "  Open http://localhost:3000 → Dashboards → MLOps"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Your ML system is now running with full observability!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════════════${NC}"
