from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)

    # Отношения
    employees = relationship("Employee", back_populates="role")  # Отношение один-ко-многим


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))  # Добавляем внешний ключ
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Отношения
    role = relationship("Role", back_populates="employees", lazy="joined")  # Отношение многие-к-одному


class Location(Base):
    __tablename__ = 'location'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    sensors = relationship("Sensor", back_populates="location")


class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(Integer, primary_key=True)
    sensor_name = Column(String, nullable=False)
    sensor_type = Column(String, nullable=False)
    status = Column(String, default="active")
    location_id = Column(Integer, ForeignKey("location.id"))

    # Отношения
    readings = relationship("SensorReading", back_populates="sensor")
    location = relationship("Location")
    settings = relationship("EquipmentSetting", back_populates="sensor")
    events = relationship("Event", back_populates="sensor")  # Добавьте эту строку


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=False)
    value = Column(String, nullable=False)  # Изменили на String вместо Float
    time = Column(DateTime, default=datetime.datetime.now)

    # Отношения
    sensor = relationship("Sensor", back_populates="readings")


class EquipmentSetting(Base):
    __tablename__ = 'equipment_settings'

    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey('sensors.id'))
    max_value = Column(Float)
    min_value = Column(Float)

    sensor = relationship("Sensor", back_populates="settings")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey("sensors.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    alert_type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    value = Column(String)
    location_id = Column(Integer, ForeignKey("location.id"))

    # Отношения
    sensor = relationship("Sensor",
                          back_populates="events")  # back_populates="events" должно соответствовать названию в Sensor
    location = relationship("Location")