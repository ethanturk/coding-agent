#!/usr/bin/env bash
# Start all services required by the agent platform.
# Usage: ./start.sh
set -e

echo "==> Starting PostgreSQL..."
pg_ctlcluster 16 main start 2>/dev/null || true
until pg_isready -q 2>/dev/null; do sleep 0.2; done
echo "    PostgreSQL is ready."

echo "==> Ensuring database exists..."
PGPASSWORD=postgres psql -U postgres -h 127.0.0.1 -tc \
  "SELECT 1 FROM pg_database WHERE datname='agent_platform'" \
  | grep -q 1 || \
  PGPASSWORD=postgres psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE agent_platform;"

echo "==> Running DB migrations..."
cd /home/user/coding-agent/backend
python3 -m app.db.init_db

echo "==> Starting backend (port 8010)..."
if fuser 8010/tcp >/dev/null 2>&1; then
  echo "    Port 8010 already in use — skipping."
else
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010 \
    > /tmp/agent-platform-backend.log 2>&1 &
  echo "    Backend PID: $!"
fi

echo "==> Starting frontend (port 3010)..."
cd /home/user/coding-agent/frontend
if fuser 3010/tcp >/dev/null 2>&1; then
  echo "    Port 3010 already in use — skipping."
else
  nohup npx --prefer-offline next dev -p 3010 --hostname 0.0.0.0 \
    > /tmp/agent-platform-frontend.log 2>&1 &
  echo "    Frontend PID: $!"
fi

# Wait for services to be reachable
echo "==> Waiting for services..."
for i in $(seq 1 30); do
  backend=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:8010/api/projects 2>/dev/null || echo "000")
  if [ "$backend" = "200" ]; then
    echo "    Backend: OK"
    break
  fi
  sleep 1
done

for i in $(seq 1 30); do
  frontend=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:3010/ 2>/dev/null || echo "000")
  if [ "$frontend" = "200" ]; then
    echo "    Frontend: OK"
    break
  fi
  sleep 1
done

echo "==> All services started."
echo "    Backend:  http://localhost:8010"
echo "    Frontend: http://localhost:3010"
