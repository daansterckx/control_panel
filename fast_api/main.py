from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from database import (
    init_database, get_database, log_activity, update_device_status,
    get_device_instances, create_device_instance, update_instance_status,
    Device, DeviceInstance, ActivityLog, SystemConfig, async_session
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app instance
app = FastAPI(
    title="PenTest Master Device API",
    description="Master device API for controlling penetration testing devices",
    version="1.0.0"
)

# Database initialization
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_database()
    logger.info("Database initialized successfully")

# CORS middleware for web control panel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your control panel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class DeviceStatus(BaseModel):
    device_id: str
    timestamp: Optional[str] = None

class DeviceCommand(BaseModel):
    command: str
    parameters: Optional[Dict[str, Any]] = {}
    device_id: str
    timestamp: str

class DeviceDetails(BaseModel):
    device_id: str
    include_instances: Optional[bool] = True

class InstanceControl(BaseModel):
    instanceId: str
    action: str

# In-memory storage for demo (replace with database in production)
device_data = {
    "keylogger": {
        "id": "device1",
        "name": "Hardware Keylogger",
        "status": "offline",
        "endpoint": "/keylogger",
        "last_seen": None,
        "instances": [],
        "device_info": {
            "buffer_size": "0 KB",
            "capture_rate": "0 keys/sec",
            "total_captured": 0
        }
    },
    "keystroke_injector": {
        "id": "device2", 
        "name": "USB Keystroke Injector",
        "status": "offline",
        "endpoint": "/keystroke-injector",
        "last_seen": None,
        "instances": [],
        "device_info": {
            "payload_loaded": "None",
            "injection_rate": "0 keys/sec",
            "total_injected": 0
        }
    },
    "ethernet_tap": {
        "id": "device3",
        "name": "Network Tap Device", 
        "status": "offline",
        "endpoint": "/ethernet-tap",
        "last_seen": None,
        "instances": [],
        "device_info": {
            "packets_captured": 0,
            "capture_rate": "0 pps",
            "interface_status": "down"
        }
    },
    "evil_twin": {
        "id": "device4",
        "name": "Rogue Access Point",
        "status": "offline", 
        "endpoint": "/evil-twin",
        "last_seen": None,
        "instances": [],
        "device_info": {
            "clients_connected": 0,
            "ssid_cloned": "None",
            "signal_strength": "0 dBm"
        }
    }
}

# Simulated MQTT message queue (replace with actual MQTT in production)
mqtt_messages = {}

# Health check endpoint
@app.get("/api/health")
async def health_check(session: AsyncSession = Depends(get_database)):
    """Master device health check with database status"""
    try:
        # Check database connectivity
        result = await session.execute(select(SystemConfig).where(SystemConfig.key == "api_version"))
        db_status = "connected" if result.scalar() else "error"
        
        # Get device count from database
        device_result = await session.execute(select(Device))
        devices_count = len(device_result.scalars().all())
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "database_status": db_status,
            "devices_count": devices_count,
            "uptime": "00:00:00"  # Implement actual uptime tracking
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "database_status": "error"
        }

# Get all devices endpoint
@app.get("/api/devices")
async def get_all_devices(session: AsyncSession = Depends(get_database)):
    """Get all registered devices from database"""
    try:
        result = await session.execute(select(Device))
        devices = result.scalars().all()
        
        return {
            "devices": [
                {
                    "device_id": device.device_id,
                    "device_type": device.device_type,
                    "name": device.name,
                    "status": device.status,
                    "last_seen": device.last_seen.isoformat() if device.last_seen else None,
                    "ip_address": device.ip_address,
                    "capabilities": device.capabilities,
                    "configuration": device.configuration
                }
                for device in devices
            ],
            "count": len(devices),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Get device instances endpoint
@app.get("/api/devices/{device_id}/instances")
async def get_device_instances_endpoint(device_id: str, session: AsyncSession = Depends(get_database)):
    """Get all instances for a specific device"""
    try:
        instances = await get_device_instances(device_id)
        
        return {
            "device_id": device_id,
            "instances": [
                {
                    "id": instance.id,
                    "instance_name": instance.instance_name,
                    "instance_type": instance.instance_type,
                    "status": instance.status,
                    "parameters": instance.parameters,
                    "started_at": instance.started_at.isoformat() if instance.started_at else None,
                    "stopped_at": instance.stopped_at.isoformat() if instance.stopped_at else None,
                    "created_by": instance.created_by
                }
                for instance in instances
            ],
            "count": len(instances),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get device instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keylogger endpoints
@app.post("/keylogger/status")
async def keylogger_status(request: DeviceStatus, session: AsyncSession = Depends(get_database)):
    """Get keylogger device status"""
    try:
        device_id = request.device_id or "keylogger-001"
        
        # Update device status in database
        await update_device_status(device_id, "online")
        
        # Get device from database
        result = await session.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar()
        
        if not device:
            # Create new keylogger device
            device = Device(
                device_id=device_id,
                device_type="keylogger",
                name="Keylogger Device",
                status="online",
                capabilities={
                    "keystroke_capture": True,
                    "real_time_monitoring": True,
                    "session_recording": True
                }
            )
            session.add(device)
            await session.commit()
            await session.refresh(device)
        
        # Get instances for this device
        instances = await get_device_instances(device_id)
        
        # Log the status check
        await log_activity(
            device_id=device_id,
            command="status_check",
            status="success"
        )
        
        # Simulate device communication (replace with actual MQTT)
        await simulate_device_communication("keylogger", "status_check")
        
        return {
            "device_id": device.device_id,
            "status": device.status,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "capabilities": device.capabilities,
            "instances": [
                {
                    "id": instance.id,
                    "name": instance.instance_name,
                    "type": instance.instance_type,
                    "status": instance.status
                }
                for instance in instances
            ],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Keylogger status check failed: {e}")
        await log_activity(
            device_id=request.device_id or "keylogger-001",
            command="status_check",
            status="error",
            response=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/keylogger/command")
async def keylogger_command(request: DeviceCommand, session: AsyncSession = Depends(get_database)):
    """Send command to keylogger device"""
    try:
        device_id = request.device_id
        
        # Get device from database
        result = await session.execute(select(Device).where(Device.device_id == device_id))
        device = result.scalar()
        
        if not device or device.status != "online":
            raise HTTPException(status_code=400, detail="Device is offline or not found")
        
        # Simulate MQTT command sending
        await simulate_device_communication("keylogger", request.command, request.parameters)
        
        # Log the command
        await log_activity(
            device_id=device_id,
            command=request.command,
            parameters=request.parameters,
            status="success"
        )
        
        logger.info(f"Sending {request.command} to keylogger {device_id}")
        
        return {
            "status": "command_sent",
            "command": request.command,
            "device_id": device_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Keylogger command failed: {e}")
        await log_activity(
            device_id=request.device_id,
            command=request.command,
            status="error",
            response=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))
        
        # Handle specific commands
        response = await handle_keylogger_command(request.command, request.parameters)
        
        return {
            "success": True,
            "command": request.command,
            "message": f"Command {request.command} sent successfully",
            "response": response
        }
    except Exception as e:
        logger.error(f"Error sending keylogger command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/keylogger/details")
async def keylogger_details(request: DeviceDetails):
    """Get detailed keylogger information"""
    try:
        device = device_data["keylogger"]
        
        return {
            "device_info": device["device_info"],
            "instances": device["instances"],
            "capabilities": ["start_logging", "stop_logging", "download_logs", "clear_buffer"],
            "last_seen": device["last_seen"],
            "status": device["status"]
        }
    except Exception as e:
        logger.error(f"Error getting keylogger details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keystroke Injector endpoints
@app.post("/keystroke-injector/status")
async def keystroke_injector_status(request: DeviceStatus):
    """Get keystroke injector device status"""
    try:
        device = device_data["keystroke_injector"]
        
        await simulate_device_communication("keystroke_injector", "status_check")
        device["last_seen"] = datetime.now().isoformat()
        
        import random
        if random.random() > 0.6:  # 40% chance of being online
            device["status"] = "online"
            if not device["instances"]:
                device["instances"] = [
                    {
                        "id": "inject_001",
                        "name": "Payload Injector",
                        "status": "stopped",
                        "details": "Ready to inject payloads"
                    }
                ]
        else:
            device["status"] = "offline"
            device["instances"] = []
        
        return {
            "status": device["status"],
            "last_seen": device["last_seen"],
            "instances": device["instances"],
            "device_info": device["device_info"]
        }
    except Exception as e:
        logger.error(f"Error getting keystroke injector status: {e}")
        return {"status": "offline", "error": str(e)}

@app.post("/keystroke-injector/command")
async def keystroke_injector_command(request: DeviceCommand):
    """Send command to keystroke injector device"""
    try:
        device = device_data["keystroke_injector"]
        
        if device["status"] != "online":
            raise HTTPException(status_code=400, detail="Device is offline")
        
        await simulate_device_communication("keystroke_injector", request.command, request.parameters)
        logger.info(f"Sending {request.command} to keystroke injector")
        
        response = await handle_keystroke_injector_command(request.command, request.parameters)
        
        return {
            "success": True,
            "command": request.command,
            "message": f"Command {request.command} sent successfully",
            "response": response
        }
    except Exception as e:
        logger.error(f"Error sending keystroke injector command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/keystroke-injector/details")
async def keystroke_injector_details(request: DeviceDetails):
    """Get detailed keystroke injector information"""
    try:
        device = device_data["keystroke_injector"]
        
        return {
            "device_info": device["device_info"],
            "instances": device["instances"],
            "capabilities": ["inject_payload", "load_script", "stop_injection", "list_payloads"],
            "payloads": ["reverse_shell.py", "credential_harvester.ps1", "keylogger.js"],
            "last_seen": device["last_seen"],
            "status": device["status"]
        }
    except Exception as e:
        logger.error(f"Error getting keystroke injector details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Ethernet Tap endpoints
@app.post("/ethernet-tap/status")
async def ethernet_tap_status(request: DeviceStatus):
    """Get ethernet tap device status"""
    try:
        device = device_data["ethernet_tap"]
        
        await simulate_device_communication("ethernet_tap", "status_check")
        device["last_seen"] = datetime.now().isoformat()
        
        import random
        if random.random() > 0.5:  # 50% chance of being online
            device["status"] = "online"
            if not device["instances"]:
                device["instances"] = [
                    {
                        "id": "tap_001",
                        "name": "Network Monitor",
                        "status": "running",
                        "details": "Capturing traffic on eth0"
                    }
                ]
        else:
            device["status"] = "offline"
            device["instances"] = []
        
        return {
            "status": device["status"],
            "last_seen": device["last_seen"],
            "instances": device["instances"],
            "device_info": device["device_info"]
        }
    except Exception as e:
        logger.error(f"Error getting ethernet tap status: {e}")
        return {"status": "offline", "error": str(e)}

@app.post("/ethernet-tap/command")
async def ethernet_tap_command(request: DeviceCommand):
    """Send command to ethernet tap device"""
    try:
        device = device_data["ethernet_tap"]
        
        if device["status"] != "online":
            raise HTTPException(status_code=400, detail="Device is offline")
        
        await simulate_device_communication("ethernet_tap", request.command, request.parameters)
        logger.info(f"Sending {request.command} to ethernet tap")
        
        response = await handle_ethernet_tap_command(request.command, request.parameters)
        
        return {
            "success": True,
            "command": request.command,
            "message": f"Command {request.command} sent successfully",
            "response": response
        }
    except Exception as e:
        logger.error(f"Error sending ethernet tap command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ethernet-tap/details")
async def ethernet_tap_details(request: DeviceDetails):
    """Get detailed ethernet tap information"""
    try:
        device = device_data["ethernet_tap"]
        
        return {
            "device_info": device["device_info"],
            "instances": device["instances"],
            "capabilities": ["start_capture", "stop_capture", "download_pcap", "monitor_mode"],
            "interfaces": ["eth0", "eth1", "wlan0"],
            "last_seen": device["last_seen"],
            "status": device["status"]
        }
    except Exception as e:
        logger.error(f"Error getting ethernet tap details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Evil Twin AP endpoints
@app.post("/evil-twin/status")
async def evil_twin_status(request: DeviceStatus):
    """Get evil twin AP device status"""
    try:
        device = device_data["evil_twin"]
        
        await simulate_device_communication("evil_twin", "status_check")
        device["last_seen"] = datetime.now().isoformat()
        
        import random
        if random.random() > 0.4:  # 60% chance of being online
            device["status"] = "online"
            if not device["instances"]:
                device["instances"] = [
                    {
                        "id": "ap_001",
                        "name": "Rogue WiFi",
                        "status": "active",
                        "details": "Broadcasting as 'Free_WiFi'"
                    }
                ]
        else:
            device["status"] = "offline"
            device["instances"] = []
        
        return {
            "status": device["status"],
            "last_seen": device["last_seen"],
            "instances": device["instances"],
            "device_info": device["device_info"]
        }
    except Exception as e:
        logger.error(f"Error getting evil twin status: {e}")
        return {"status": "offline", "error": str(e)}

@app.post("/evil-twin/command")
async def evil_twin_command(request: DeviceCommand):
    """Send command to evil twin AP device"""
    try:
        device = device_data["evil_twin"]
        
        if device["status"] != "online":
            raise HTTPException(status_code=400, detail="Device is offline")
        
        await simulate_device_communication("evil_twin", request.command, request.parameters)
        logger.info(f"Sending {request.command} to evil twin AP")
        
        response = await handle_evil_twin_command(request.command, request.parameters)
        
        return {
            "success": True,
            "command": request.command,
            "message": f"Command {request.command} sent successfully",
            "response": response
        }
    except Exception as e:
        logger.error(f"Error sending evil twin command: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evil-twin/details")
async def evil_twin_details(request: DeviceDetails):
    """Get detailed evil twin AP information"""
    try:
        device = device_data["evil_twin"]
        
        return {
            "device_info": device["device_info"],
            "instances": device["instances"],
            "capabilities": ["start_ap", "stop_ap", "view_clients", "deauth_clients", "clone_network"],
            "available_networks": ["Corporate_WiFi", "Guest_Network", "Home_Router"],
            "last_seen": device["last_seen"],
            "status": device["status"]
        }
    except Exception as e:
        logger.error(f"Error getting evil twin details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Command handlers
async def handle_keylogger_command(command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Handle keylogger-specific commands"""
    if command == "start_logging":
        return {"message": "Keylogging started", "buffer_size": "0 KB"}
    elif command == "stop_logging":
        return {"message": "Keylogging stopped", "keys_captured": 1247}
    elif command == "download_logs":
        return {
            "message": "Logs ready for download",
            "download_url": "/downloads/keylog_20240922.txt",
            "filename": "keylog_20240922.txt",
            "size": "45 KB"
        }
    elif command == "clear_buffer":
        return {"message": "Buffer cleared", "keys_cleared": 892}
    elif command == "control_instance":
        instance_id = parameters.get("instanceId")
        action = parameters.get("action")
        return {"message": f"Instance {instance_id} {action} successful"}
    else:
        return {"message": f"Command {command} executed"}

async def handle_keystroke_injector_command(command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Handle keystroke injector-specific commands"""
    if command == "inject_payload":
        return {"message": "Payload injection started", "estimated_time": "30 seconds"}
    elif command == "load_script":
        return {"message": "Script loaded successfully", "script_name": "reverse_shell.py"}
    elif command == "stop_injection":
        return {"message": "Injection stopped", "keys_injected": 543}
    elif command == "list_payloads":
        return {
            "message": "Payloads listed",
            "payloads": ["reverse_shell.py", "credential_harvester.ps1", "keylogger.js"]
        }
    elif command == "control_instance":
        instance_id = parameters.get("instanceId")
        action = parameters.get("action")
        return {"message": f"Instance {instance_id} {action} successful"}
    else:
        return {"message": f"Command {command} executed"}

async def handle_ethernet_tap_command(command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Handle ethernet tap-specific commands"""
    if command == "start_capture":
        return {"message": "Packet capture started", "interface": "eth0"}
    elif command == "stop_capture":
        return {"message": "Packet capture stopped", "packets_captured": 15432}
    elif command == "download_pcap":
        return {
            "message": "PCAP ready for download",
            "download_url": "/downloads/capture_20240922.pcap",
            "filename": "capture_20240922.pcap",
            "size": "2.3 MB"
        }
    elif command == "monitor_mode":
        return {"message": "Monitor mode enabled", "interface": "wlan0"}
    elif command == "control_instance":
        instance_id = parameters.get("instanceId")
        action = parameters.get("action")
        return {"message": f"Instance {instance_id} {action} successful"}
    else:
        return {"message": f"Command {command} executed"}

async def handle_evil_twin_command(command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Handle evil twin AP-specific commands"""
    if command == "start_ap":
        return {"message": "Evil Twin AP started", "ssid": "Free_WiFi"}
    elif command == "stop_ap":
        return {"message": "Evil Twin AP stopped", "clients_disconnected": 3}
    elif command == "view_clients":
        return {
            "message": "Connected clients listed",
            "clients": [
                {"mac": "aa:bb:cc:dd:ee:f1", "ip": "192.168.4.100", "hostname": "laptop-user1"},
                {"mac": "aa:bb:cc:dd:ee:f2", "ip": "192.168.4.101", "hostname": "phone-user2"}
            ]
        }
    elif command == "deauth_clients":
        return {"message": "Deauth attack initiated", "targets": 2}
    elif command == "clone_network":
        return {"message": "Network cloned successfully", "original_ssid": "Corporate_WiFi"}
    elif command == "control_instance":
        instance_id = parameters.get("instanceId")
        action = parameters.get("action")
        return {"message": f"Instance {instance_id} {action} successful"}
    else:
        return {"message": f"Command {command} executed"}

# Utility functions
async def simulate_device_communication(device_type: str, command: str, parameters: Dict[str, Any] = None):
    """Simulate MQTT communication with devices (replace with actual MQTT)"""
    logger.info(f"MQTT -> {device_type}: {command} {parameters or ''}")
    
    # Simulate network delay
    await asyncio.sleep(0.1)
    
    # Store message for potential response handling
    message_id = str(uuid.uuid4())
    mqtt_messages[message_id] = {
        "device_type": device_type,
        "command": command,
        "parameters": parameters,
        "timestamp": datetime.now().isoformat(),
        "status": "sent"
    }
    
    return message_id

# Download endpoints (for log files, pcap files, etc.)
@app.get("/downloads/{filename}")
async def download_file(filename: str):
    """Download captured files"""
    # In production, implement proper file serving with security checks
    file_path = f"/tmp/{filename}"  # Replace with actual file storage path
    
    if not os.path.exists(file_path):
        # Create dummy file for demo
        with open(file_path, "w") as f:
            f.write(f"Dummy content for {filename}\nGenerated at: {datetime.now().isoformat()}")
    
    return FileResponse(file_path, filename=filename)

# WebSocket endpoint for real-time updates (optional)
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """WebSocket for real-time device updates"""
    await websocket.accept()
    try:
        while True:
            # Send periodic status updates
            status_update = {
                "type": "status_update",
                "timestamp": datetime.now().isoformat(),
                "devices": {k: {"status": v["status"], "last_seen": v["last_seen"]} 
                           for k, v in device_data.items()}
            }
            await websocket.send_json(status_update)
            await asyncio.sleep(5)  # Send updates every 5 seconds
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)