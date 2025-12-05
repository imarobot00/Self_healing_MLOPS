#!/bin/bash
# Quick start script for the data pipeline
# Usage: ./quickstart.sh [docker|local|test]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASET_DIR="$PROJECT_ROOT/dataset"

show_help() {
    echo "Data Pipeline Quick Start"
    echo ""
    echo "Usage: ./quickstart.sh [command]"
    echo ""
    echo "Commands:"
    echo "  docker     - Start pipeline in Docker (recommended)"
    echo "  local      - Start pipeline locally"
    echo "  test       - Run component tests"
    echo "  once       - Run pipeline once (no scheduling)"
    echo "  validate   - Validate existing data"
    echo "  stop       - Stop Docker containers"
    echo "  logs       - View Docker logs"
    echo "  help       - Show this help message"
    echo ""
}

check_env() {
    if [ ! -f "$DATASET_DIR/.env" ]; then
        echo "⚠️  No .env file found. Creating from template..."
        cp "$DATASET_DIR/.env.example" "$DATASET_DIR/.env"
        echo "✅ Created .env file. Please edit it to add your API key:"
        echo "   nano $DATASET_DIR/.env"
        echo ""
    fi
}

install_deps() {
    echo "📦 Installing Python dependencies..."
    cd "$DATASET_DIR"
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
}

docker_start() {
    echo "🐳 Starting pipeline in Docker..."
    check_env
    cd "$PROJECT_ROOT"
    docker-compose up -d
    echo ""
    echo "✅ Pipeline started!"
    echo "   View logs: docker-compose logs -f data-pipeline"
    echo "   Stop: docker-compose down"
}

docker_stop() {
    echo "🛑 Stopping Docker containers..."
    cd "$PROJECT_ROOT"
    docker-compose down
    echo "✅ Stopped"
}

docker_logs() {
    cd "$PROJECT_ROOT"
    docker-compose logs -f data-pipeline
}

local_start() {
    echo "🚀 Starting pipeline locally..."
    check_env
    install_deps
    cd "$DATASET_DIR"
    
    # Load environment variables
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    echo ""
    echo "Starting scheduler (press Ctrl+C to stop)..."
    python scheduler.py --mode interval --interval 2
}

run_once() {
    echo "🔄 Running pipeline once..."
    check_env
    install_deps
    cd "$DATASET_DIR"
    
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    python incremental_loader.py --locations 3459 6093549 6093550 6093551 6093552 6093553 6093554 6093555 6093556
    echo ""
    echo "✅ Pipeline run completed"
    echo "   Check data files: ls -lh $DATASET_DIR/location_*.json"
    echo "   View state: cat $DATASET_DIR/.state.json"
}

run_test() {
    echo "🧪 Running component tests..."
    install_deps
    cd "$DATASET_DIR"
    python test_pipeline.py
}

validate_data() {
    echo "✅ Validating data quality..."
    install_deps
    cd "$DATASET_DIR"
    
    if [ ! -f location_3459.json ]; then
        echo "❌ No data files found. Run pipeline first: ./quickstart.sh once"
        exit 1
    fi
    
    python validator.py --file location_3459.json --sample 1000
}

# Main logic
case "${1:-help}" in
    docker)
        docker_start
        ;;
    local)
        local_start
        ;;
    test)
        run_test
        ;;
    once)
        run_once
        ;;
    validate)
        validate_data
        ;;
    stop)
        docker_stop
        ;;
    logs)
        docker_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
