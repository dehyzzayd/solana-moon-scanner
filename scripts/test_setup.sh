#!/bin/bash
# Test setup script for Solana Moon Scanner

set -e

echo "🧪 Testing Solana Moon Scanner Setup"
echo "====================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "1. Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
else
    echo -e "${RED}✗${NC} Python 3 not found"
    exit 1
fi

# Check if .env exists
echo ""
echo "2. Checking configuration..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file found"
    
    # Check for required variables
    MISSING_VARS=()
    
    if ! grep -q "QUICKNODE_RPC_URL\|HELIUS_RPC_URL" .env; then
        MISSING_VARS+=("RPC URL (QUICKNODE_RPC_URL or HELIUS_RPC_URL)")
    fi
    
    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠${NC} Missing configuration:"
        for var in "${MISSING_VARS[@]}"; do
            echo "   - $var"
        done
    else
        echo -e "${GREEN}✓${NC} Required configuration found"
    fi
else
    echo -e "${YELLOW}⚠${NC} .env file not found"
    echo "   Copy config.example.env to .env and configure it"
fi

# Check if virtual environment exists
echo ""
echo "3. Checking virtual environment..."
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment found"
else
    echo -e "${YELLOW}⚠${NC} Virtual environment not found"
    echo "   Run: python3 -m venv venv"
fi

# Check dependencies
echo ""
echo "4. Checking dependencies..."
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || true
    
    if python3 -c "import solana" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Dependencies installed"
    else
        echo -e "${YELLOW}⚠${NC} Dependencies not installed"
        echo "   Run: pip install -r requirements.txt"
    fi
else
    echo -e "${YELLOW}⚠${NC} Cannot check dependencies (no venv)"
fi

# Test import of main modules
echo ""
echo "5. Testing module imports..."
if python3 -c "from src.scanner import MoonScanner" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Core modules can be imported"
else
    echo -e "${RED}✗${NC} Failed to import core modules"
    echo "   Check Python path and dependencies"
fi

# Check Docker
echo ""
echo "6. Checking Docker (optional)..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    echo -e "${GREEN}✓${NC} Docker $DOCKER_VERSION found"
    
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f4 | tr -d ',')
        echo -e "${GREEN}✓${NC} Docker Compose $COMPOSE_VERSION found"
    else
        echo -e "${YELLOW}⚠${NC} Docker Compose not found (optional)"
    fi
else
    echo -e "${YELLOW}⚠${NC} Docker not found (optional)"
fi

# Check directory structure
echo ""
echo "7. Checking directory structure..."
REQUIRED_DIRS=("src" "src/core" "src/scoring" "src/alerts" "src/utils" "tests")
MISSING_DIRS=()

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All required directories present"
else
    echo -e "${RED}✗${NC} Missing directories:"
    for dir in "${MISSING_DIRS[@]}"; do
        echo "   - $dir"
    done
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo -e "${GREEN}✓${NC} Created logs directory"
fi

# Summary
echo ""
echo "====================================="
echo "Setup Test Complete"
echo "====================================="
echo ""

# Run quick configuration check
echo "Configuration Summary:"
if [ -f ".env" ]; then
    python3 -m src.cli config 2>/dev/null || echo "Cannot display config (missing dependencies or config issues)"
else
    echo "No .env file found - please configure before running"
fi

echo ""
echo "Next Steps:"
echo "  1. Ensure .env is configured with your API keys"
echo "  2. Install dependencies: pip install -r requirements.txt"
echo "  3. Run tests: pytest"
echo "  4. Test alerts: python -m src.cli test-alerts"
echo "  5. Start monitoring: python -m src.cli monitor"
echo ""
