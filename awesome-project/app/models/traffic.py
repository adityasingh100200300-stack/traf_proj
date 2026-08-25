from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.models.base import Base

class Intersection(Base):
    __tablename__ = "intersections"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # PostGIS point for geospatial emergency routing
    location = Column(Geometry(geometry_type='POINT', srid=4326)) 
    
    lanes = relationship("Lane", back_populates="intersection")
    phases = relationship("SignalPhase", back_populates="intersection")

class Lane(Base):
    __tablename__ = "lanes"

    id = Column(String, primary_key=True, index=True)
    intersection_id = Column(String, ForeignKey("intersections.id"), nullable=False)
    direction = Column(String, nullable=False) # e.g., "north_south"
    
    intersection = relationship("Intersection", back_populates="lanes")

class SignalPhase(Base):
    __tablename__ = "signal_phases"

    id = Column(String, primary_key=True, index=True)
    intersection_id = Column(String, ForeignKey("intersections.id"), nullable=False)
    phase_name = Column(String, nullable=False)
    min_green = Column(Integer, default=10)
    max_green = Column(Integer, default=60)

    intersection = relationship("Intersection", back_populates="phases")