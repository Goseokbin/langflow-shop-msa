from sqlalchemy import Column, String, Integer, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from .database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    description = Column(String)
    price = Column(Numeric(10, 2), nullable=False)
    category = Column(String, nullable=False, index=True)
    inventory = Column(Integer, nullable=False, default=0)
    image_url = Column(String)
    # Detailed product information
    detailed_description = Column(String)
    specifications = Column(String)  # JSON string
    brand = Column(String)
    rating = Column(Numeric(3, 2), default=0.0)
    review_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Made with Bob
