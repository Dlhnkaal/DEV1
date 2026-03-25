#!/usr/bin/env bash
set -e

docker-compose down 

docker-compose up -d --build

docker-compose up

echo "Services started!"