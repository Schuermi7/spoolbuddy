#!/bin/sh

cd backend
ruff check && ruff format --check

if [ "$1" = "--full" ]; then
  python -m pytest tests/ -v -n auto
else
  python -m pytest tests/ -v -n auto
fi
cd ..
