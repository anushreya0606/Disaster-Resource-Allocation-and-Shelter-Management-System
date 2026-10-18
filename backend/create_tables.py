from database import Base, engine

# Import all models so SQLAlchemy knows about the tables
from models.evacuee import Evacuee
from models.resource import Resource
from models.alert import Alert

# Create tables
Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")