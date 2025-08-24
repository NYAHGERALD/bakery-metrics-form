#!/bin/bash

# Complete Database Migration Script - SECURE VERSION
# No hardcoded credentials - uses environment variables only
# Date: 2025-08-24

# Color definitions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Secure Database Migration Script${NC}"
echo "======================================"

# Check required environment variables
echo -e "${YELLOW}🔍 Checking environment variables...${NC}"

required_vars=("LOCAL_DB_PASSWORD" "RENDER_DB_HOST" "RENDER_DB_USER" "RENDER_DB_PASSWORD")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        missing_vars+=("$var")
    fi
done

if [[ ${#missing_vars[@]} -gt 0 ]]; then
    echo -e "${RED}❌ Missing required environment variables:${NC}"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo -e "${YELLOW}💡 Set them like this:${NC}"
    echo "export LOCAL_DB_PASSWORD='your_local_password'"
    echo "export RENDER_DB_HOST='your-render-host.com'"
    echo "export RENDER_DB_USER='your_render_user'"
    echo "export RENDER_DB_PASSWORD='your_render_password'"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ All required environment variables are set${NC}"

# Database configurations using environment variables
LOCAL_HOST="${LOCAL_DB_HOST:-localhost}"
LOCAL_DB="${LOCAL_DB_NAME:-bakery_metrics_db}"
LOCAL_USER="${LOCAL_DB_USER:-bakery_users}"
LOCAL_PASSWORD="${LOCAL_DB_PASSWORD}"
LOCAL_PORT="${LOCAL_DB_PORT:-5432}"

RENDER_HOST="${RENDER_DB_HOST}"
RENDER_DB="${RENDER_DB_NAME:-bakery_metrics_db}"
RENDER_USER="${RENDER_DB_USER}"
RENDER_PASSWORD="${RENDER_DB_PASSWORD}"
RENDER_PORT="${RENDER_DB_PORT:-5432}"

echo -e "${BLUE}📊 Migration Configuration:${NC}"
echo "  Local:  $LOCAL_USER@$LOCAL_HOST:$LOCAL_PORT/$LOCAL_DB"
echo "  Render: $RENDER_USER@$RENDER_HOST:$RENDER_PORT/$RENDER_DB"
echo ""

# Generate backup filename with timestamp
BACKUP_FILE="migration_backup_$(date +%Y%m%d_%H%M%S).sql"

echo -e "${YELLOW}📦 Creating backup: $BACKUP_FILE${NC}"
export PGPASSWORD="$LOCAL_PASSWORD"
pg_dump -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" \
    --verbose --clean --no-owner --no-privileges > "$BACKUP_FILE"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ Backup created successfully${NC}"
else
    echo -e "${RED}❌ Backup failed${NC}"
    exit 1
fi

echo -e "${YELLOW}📤 Uploading to Render database...${NC}"
export PGPASSWORD="$RENDER_PASSWORD"
psql -h "$RENDER_HOST" -p "$RENDER_PORT" -U "$RENDER_USER" -d "$RENDER_DB" -f "$BACKUP_FILE"

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ Migration completed successfully!${NC}"
    echo -e "${BLUE}📁 Backup saved as: $BACKUP_FILE${NC}"
else
    echo -e "${RED}❌ Migration failed${NC}"
    exit 1
fi