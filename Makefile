.PHONY: help build up down restart logs ps test clean deploy deploy-prod deploy-scheduler

# Default target
help:
	@echo "Horse Racing Tool - Docker Management Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo "  build              - Build Docker images"
	@echo "  up                 - Start all containers"
	@echo "  down               - Stop all containers"
	@echo "  restart            - Restart all containers"
	@echo "  logs               - View container logs"
	@echo "  logs-backend       - View backend logs only"
	@echo "  logs-scheduler     - View scheduler logs only"
	@echo "  ps                 - List running containers"
	@echo "  test               - Run integration tests"
	@echo "  clean              - Remove containers and volumes"
	@echo "  deploy             - Deploy full stack (dev)"
	@echo "  deploy-prod        - Deploy full stack (production)"
	@echo "  deploy-scheduler   - Deploy scheduler only"
	@echo "  health             - Check backend health"
	@echo "  crawl              - Manually trigger crawler"
	@echo "  shell-backend      - Shell into backend container"
	@echo "  shell-scheduler    - Shell into scheduler container"

# Build images
build:
	@echo "Building Docker images..."
	docker-compose build --no-cache

# Start containers
up:
	@echo "Starting containers..."
	docker-compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@make ps

# Stop containers
down:
	@echo "Stopping containers..."
	docker-compose down

# Restart containers
restart:
	@echo "Restarting containers..."
	docker-compose restart
	@sleep 3
	@make ps

# View logs
logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-scheduler:
	docker-compose logs -f scheduler

# List containers
ps:
	@docker-compose ps
	@echo ""
	@docker stats --no-stream

# Test endpoints
test:
	@echo "Testing backend health..."
	@curl -s http://localhost:5001/api/health | python3 -m json.tool
	@echo ""
	@echo "Testing today's races endpoint..."
	@curl -s http://localhost:5001/api/todays-races | python3 -m json.tool | head -20

# Clean up
clean:
	@echo "Removing containers and volumes..."
	docker-compose down -v
	@echo "Cleaning up dangling images..."
	docker image prune -f

# Deploy full stack (dev)
deploy:
	@echo "Deploying full stack (development)..."
	@make build
	@make up
	@echo "Deployment complete!"
	@make health

# Deploy full stack (production)
deploy-prod:
	@echo "Deploying full stack (production)..."
	docker-compose -f docker-compose.prod.yml build --no-cache
	docker-compose -f docker-compose.prod.yml up -d
	@echo "Production deployment complete!"
	@sleep 5
	@make health

# Deploy scheduler only
deploy-scheduler:
	@echo "Deploying scheduler only..."
	docker-compose -f docker-compose.scheduler.yml up -d
	@echo "Scheduler deployment complete!"

# Check health
health:
	@echo "Checking backend health..."
	@curl -s http://localhost:5001/api/health || echo "Backend not responding"
	@echo ""
	@echo "Checking container status..."
	@docker ps --filter "name=horse-racing" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Manual crawler run
crawl:
	@echo "Triggering manual crawl for yesterday..."
	docker-compose exec scheduler python3 /app/backend/daily_crawl.py

# Shell access
shell-backend:
	docker-compose exec backend /bin/bash

shell-scheduler:
	docker-compose exec scheduler /bin/bash

# View crawler logs
crawler-logs:
	docker-compose exec scheduler tail -f /var/log/horse-racing-crawler.log
