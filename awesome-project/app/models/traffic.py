from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Index, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from geoalchemy2 import Geometry
from app.models.base import Base

class Intersection(Base):
    __tablename__ = "intersections"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(Geometry(geometry_type='POINT', srid=4326), nullable=True)
    
    lanes = relationship("Lane", back_populates="intersection", cascade="all, delete-orphan")
    phases = relationship("SignalPhase", back_populates="intersection", cascade="all, delete-orphan")
    telemetry = relationship("TrafficTelemetry", back_populates="intersection", cascade="all, delete-orphan")
    emergency_events = relationship("EmergencyEvent", back_populates="intersection")

class Lane(Base):
    __tablename__ = "lanes"

    id = Column(String, primary_key=True, index=True)
    intersection_id = Column(String, ForeignKey("intersections.id"), nullable=False)
    direction = Column(String, nullable=False)  # e.g., "north_left", "east_straight"
    
    intersection = relationship("Intersection", back_populates="lanes")

class SignalPhase(Base):
    __tablename__ = "signal_phases"

    id = Column(String, primary_key=True, index=True)
    intersection_id = Column(String, ForeignKey("intersections.id"), nullable=False)
    phase_name = Column(String, nullable=False)
    min_green = Column(Integer, default=10)
    max_green = Column(Integer, default=60)

    intersection = relationship("Intersection", back_populates="phases")

class TrafficTelemetry(Base):
    __tablename__ = "traffic_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    intersection_id = Column(String, ForeignKey("intersections.id"), nullable=False, index=True)
    lane_id = Column(String, nullable=False, index=True)
    vehicle_count = Column(Integer, nullable=False, default=0)
    average_speed = Column(Float, nullable=False, default=0.0)
    queue_length = Column(Float, nullable=False, default=0.0)
    occupancy = Column(Float, nullable=False, default=0.0)

    intersection = relationship("Intersection", back_populates="telemetry")

    __table_args__ = (
        Index("ix_traffic_telemetry_ts_intersection", "timestamp", "intersection_id"),
    )

class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String, nullable=False, index=True)
    vehicle_type = Column(String, nullable=False)  # e.g., "ambulance", "fire_truck"
    intersection_id = Column(String, ForeignKey("intersections.id"), nullable=False, index=True)
    override_phase = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    intersection = relationship("Intersection", back_populates="emergency_events")