#!/bin/bash
# Railway startup script

# Use PORT environment variable or default to 8000
PORT=${PORT:-8000}

echo "Starting Solana Moon Scanner on port $PORT"

# Start uvicorn with the port
uvicorn webapp.main:app --host 0.0.0.0 --port $PORT
