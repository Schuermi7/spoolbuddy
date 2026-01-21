#!/bin/bash

cd backend
python -m pytest tests/ -v           # All tests
cd ..
