#!/usr/bin/env bash
set -e

docker compose exec -T redpanda rpk topic create moderation -p 3 || true
docker compose exec -T redpanda rpk topic create moderation_dlq -p 3 || true
echo "Topics created!"