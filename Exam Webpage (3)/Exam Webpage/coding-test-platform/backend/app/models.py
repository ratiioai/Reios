"""Shared SQLAlchemy base. The Reios tables are defined in app/reios/models.py."""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
