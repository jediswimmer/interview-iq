#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${CYAN}🎯 InterviewIQ — Starting...${NC}"

# Check Python venv
if [ ! -d "venv" ]; then
    echo -e "${CYAN}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

source venv/bin/activate

# Install Python deps
echo -e "${CYAN}Installing Python dependencies...${NC}"
pip install -r backend/requirements.txt -q

# Install frontend deps if needed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${CYAN}Installing frontend dependencies...${NC}"
    cd frontend && npm install && cd ..
fi

# Start backend
echo -e "${GREEN}Starting backend on :8000...${NC}"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
echo -e "${GREEN}Starting frontend on :3000...${NC}"
cd frontend && npm run dev -- --host &
FRONTEND_PID=$!

cd "$DIR"

echo -e ""
echo -e "${GREEN}✅ InterviewIQ is running!${NC}"
echo -e "   Frontend: ${CYAN}http://localhost:3000${NC}"
echo -e "   Backend:  ${CYAN}http://localhost:8000${NC}"
echo -e ""
echo -e "   Press Ctrl+C to stop"

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
