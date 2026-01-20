from db import engine
from models import Base

Base.metadata.create_all(bind=engine)
print("DB tables created/verified.")
