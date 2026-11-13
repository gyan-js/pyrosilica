#!/usr/bin/env bash
set -e

MODEL=${1:?Usage: record_run.sh <model_file> [run_name]}
RUN_NAME=${2:-run_$(date +%Y%m%d_%H%M%S)}
REPLAY_PATH="stream-server/replays/${RUN_NAME}.ndjson"

mkdir -p stream-server/replays

echo "[record_run] starting stream-server (recording to ${REPLAY_PATH})"
RECORD_TO="$REPLAY_PATH" node stream-server/server.js &
SERVER_PID=$!
sleep 1  

echo "[record_run] starting telemetry-engine"
python telemetry-engine/main.py &
TELEMETRY_PID=$!

echo "[record_run] starting training-harness"
python training-harness/main.py --model "$MODEL"
TRAINING_EXIT=$?

echo "[record_run] training finished, shutting down"
kill $TELEMETRY_PID 2>/dev/null || true
kill -SIGINT $SERVER_PID 2>/dev/null  
wait $SERVER_PID 2>/dev/null || true

echo "[record_run] saved replay: ${REPLAY_PATH}"
exit $TRAINING_EXIT