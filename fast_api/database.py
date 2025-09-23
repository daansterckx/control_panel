"""
Database models and connection for the penetration testing control panel.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime
import json
import aiosqlite

# Database URL for SQLite
DATABASE_URL = "sqlite+aiosqlite:///./pentesting_control.db"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class Device(Base):
    """Device information table"""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_type = Column(String(50), nullable=False)  # keylogger, keystroke-injector, etc.
    device_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(20), default="offline")  # online, offline, error
    last_seen = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    mac_address = Column(String(17))
    capabilities = Column(JSON)  # Device-specific capabilities
    configuration = Column(JSON)  # Current configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DeviceInstance(Base):
    """Active device instances table"""
    __tablename__ = "device_instances"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), nullable=False)
    instance_name = Column(String(200), nullable=False)
    instance_type = Column(String(50), nullable=False)  # session, capture, injection, etc.
    status = Column(String(20), default="stopped")  # running, stopped, paused, error
    parameters = Column(JSON)  # Instance-specific parameters
    started_at = Column(DateTime, default=datetime.utcnow)
    stopped_at = Column(DateTime)
    created_by = Column(String(100))  # User who created the instance
    
class ActivityLog(Base):
    """Activity and command log table"""
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(100), nullable=False)
    instance_id = Column(Integer)  # Reference to device_instances.id
    command = Column(String(500), nullable=False)
    parameters = Column(JSON)
    response = Column(Text)
    status = Column(String(20), nullable=False)  # success, error, pending
    execution_time = Column(Integer)  # Execution time in milliseconds
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(100))

class SystemConfig(Base):
    """System configuration table"""
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String(500))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100))

class UserSession(Base):
    """User session management table"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False)
    user_id = Column(String(100), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)

# Database dependency
async def get_database():
    """Get database session"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_database():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Insert default configuration
    async with async_session() as session:
        # Check if config already exists
        from sqlalchemy import select
        result = await session.execute(select(SystemConfig).where(SystemConfig.key == "master_device_id"))
        if not result.scalar():
            default_configs = [
                SystemConfig(
                    key="master_device_id",
                    value="master-001",
                    description="Master device identifier"
                ),
                SystemConfig(
                    key="mqtt_broker_host",
                    value="localhost",
                    description="MQTT broker host address"
                ),
                SystemConfig(
                    key="mqtt_broker_port",
                    value="1883",
                    description="MQTT broker port"
                ),
                SystemConfig(
                    key="api_version",
                    value="1.0.0",
                    description="API version"
                ),
                SystemConfig(
                    key="session_timeout",
                    value="3600",
                    description="Session timeout in seconds"
                )
            ]
            
            for config in default_configs:
                session.add(config)
            
            await session.commit()

# Utility functions
async def log_activity(device_id: str, command: str, parameters: dict = None, 
                      response: str = None, status: str = "success", 
                      execution_time: int = None, instance_id: int = None,
                      user_id: str = None):
    """Log device activity"""
    async with async_session() as session:
        log_entry = ActivityLog(
            device_id=device_id,
            instance_id=instance_id,
            command=command,
            parameters=parameters,
            response=response,
            status=status,
            execution_time=execution_time,
            user_id=user_id
        )
        session.add(log_entry)
        await session.commit()

async def update_device_status(device_id: str, status: str, ip_address: str = None):
    """Update device status and last seen timestamp"""
    async with async_session() as session:
        from sqlalchemy import select, update
        
        # Update existing device or create new one
        result = await session.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar()
        
        if device:
            device.status = status
            device.last_seen = datetime.utcnow()
            if ip_address:
                device.ip_address = ip_address
        else:
            # Create new device entry
            device_type = device_id.split('-')[0] if '-' in device_id else "unknown"
            device = Device(
                device_id=device_id,
                device_type=device_type,
                name=f"{device_type.title()} Device",
                status=status,
                ip_address=ip_address
            )
            session.add(device)
        
        await session.commit()

async def get_device_instances(device_id: str):
    """Get active instances for a device"""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(DeviceInstance).where(DeviceInstance.device_id == device_id)
        )
        return result.scalars().all()

async def create_device_instance(device_id: str, instance_name: str, 
                                instance_type: str, parameters: dict = None,
                                created_by: str = None):
    """Create a new device instance"""
    async with async_session() as session:
        instance = DeviceInstance(
            device_id=device_id,
            instance_name=instance_name,
            instance_type=instance_type,
            parameters=parameters,
            created_by=created_by
        )
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

async def update_instance_status(instance_id: int, status: str):
    """Update instance status"""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(DeviceInstance).where(DeviceInstance.id == instance_id))
        instance = result.scalar()
        
        if instance:
            instance.status = status
            if status == "stopped":
                instance.stopped_at = datetime.utcnow()
            await session.commit()
