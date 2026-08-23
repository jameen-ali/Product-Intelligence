#!/usr/bin/env python3
"""
Standalone execution script to seed demonstration data into PostgreSQL, Qdrant, and Neo4j.
"""
import sys
import os

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.db import SessionLocal, Base, engine
from app.services.seed_service import seed_demo_data

def main():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Seeding demonstration products...")
        seed_demo_data(db)
        print("Seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
