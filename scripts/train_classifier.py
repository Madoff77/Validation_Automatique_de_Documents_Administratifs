#!/usr/bin/env python3
"""
Standalone script to train the ML document classifier.
Run inside the backend container: docker compose exec backend-api python scripts/train_classifier.py
Or via: make train
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from pipeline.classification.train import main

if __name__ == '__main__':
    main()
