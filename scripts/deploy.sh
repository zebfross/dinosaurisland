#!/bin/bash
# Deploy Dinosaur Island to A2 Hosting (inceptify.com/dinosaurisland)
#
# Usage: ./scripts/deploy.sh
#
# Prerequisites:
#   - SSH alias "redify" configured in ~/.ssh/config
#   - Python app created in cPanel at inceptify.com/dinosaurisland (Python 3.11)
#   - Node.js installed locally for frontend build

set -e

REMOTE="redify"
REMOTE_PATH="/home/odionfro/inceptify.com/dinosaurisland"
VENV_ACTIVATE="source /home/odionfro/virtualenv/inceptify.com/dinosaurisland/3.11/bin/activate"

echo "=== Building frontend ==="
cd client
VITE_BASE_PATH=/dinosaurisland/ npx vite build
cd ..

echo ""
echo "=== Uploading to server ==="
rsync -avz --delete \
  --exclude='.venv' \
  --exclude='node_modules' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='design' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='stderr.log' \
  ./ ${REMOTE}:${REMOTE_PATH}/

echo ""
echo "=== Installing dependencies ==="
ssh ${REMOTE} "${VENV_ACTIVATE} && cd ${REMOTE_PATH} && pip install -r requirements.txt -q"

echo ""
echo "=== Restarting app ==="
ssh ${REMOTE} "touch ${REMOTE_PATH}/tmp/restart.txt"

echo ""
echo "=== Verifying ==="
sleep 3
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -m 10 https://inceptify.com/dinosaurisland/api/health)
if [ "$STATUS" = "200" ]; then
  echo "Deploy successful! https://inceptify.com/dinosaurisland/"
else
  echo "Warning: Health check returned HTTP ${STATUS}"
  echo "Check logs: ssh ${REMOTE} 'cat ${REMOTE_PATH}/stderr.log'"
fi
