#!/usr/bin/env python3
"""
Simple test script for PenTest Master Device API
"""

import requests
import json
import time
from datetime import datetime

API_BASE = "http://localhost:8080"

def test_health_check():
    """Test the health check endpoint"""
    print("🏥 Testing health check...")
    response = requests.get(f"{API_BASE}/api/health")
    if response.status_code == 200:
        print("✅ Health check passed")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Health check failed: {response.status_code}")
    return response.status_code == 200

def test_device_status(device_type):
    """Test device status endpoint"""
    print(f"📊 Testing {device_type} status...")
    
    endpoint = f"{API_BASE}/{device_type}/status"
    payload = {
        "device_id": f"device{['keylogger', 'keystroke-injector', 'ethernet-tap', 'evil-twin'].index(device_type) + 1}",
        "timestamp": datetime.now().isoformat()
    }
    
    response = requests.post(endpoint, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {device_type} status: {data.get('status', 'unknown')}")
        if data.get('instances'):
            print(f"   Instances: {len(data['instances'])}")
    else:
        print(f"❌ {device_type} status failed: {response.status_code}")
    
    return response.status_code == 200

def test_device_command(device_type, command):
    """Test sending a command to a device"""
    print(f"⚡ Testing {device_type} command: {command}...")
    
    endpoint = f"{API_BASE}/{device_type}/command"
    payload = {
        "command": command,
        "parameters": {},
        "device_id": f"device{['keylogger', 'keystroke-injector', 'ethernet-tap', 'evil-twin'].index(device_type) + 1}",
        "timestamp": datetime.now().isoformat()
    }
    
    response = requests.post(endpoint, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Command sent successfully: {data.get('message', 'No message')}")
    else:
        print(f"❌ Command failed: {response.status_code}")
        if response.status_code == 400:
            print(f"   Error: {response.json().get('detail', 'Unknown error')}")
    
    return response.status_code == 200

def test_device_details(device_type):
    """Test device details endpoint"""
    print(f"📋 Testing {device_type} details...")
    
    endpoint = f"{API_BASE}/{device_type}/details"
    payload = {
        "device_id": f"device{['keylogger', 'keystroke-injector', 'ethernet-tap', 'evil-twin'].index(device_type) + 1}",
        "include_instances": True
    }
    
    response = requests.post(endpoint, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {device_type} details retrieved")
        print(f"   Capabilities: {len(data.get('capabilities', []))}")
    else:
        print(f"❌ {device_type} details failed: {response.status_code}")
    
    return response.status_code == 200

def main():
    """Run all tests"""
    print("🛡️  PenTest Master Device API Test Suite")
    print("=" * 50)
    
    # Test health check
    if not test_health_check():
        print("❌ Health check failed. Is the API server running?")
        print("   Start with: ./start_api.sh")
        return
    
    print()
    
    # Test all devices
    devices = ["keylogger", "keystroke-injector", "ethernet-tap", "evil-twin"]
    commands = {
        "keylogger": "start_logging",
        "keystroke-injector": "inject_payload", 
        "ethernet-tap": "start_capture",
        "evil-twin": "start_ap"
    }
    
    for device in devices:
        print(f"\n🎯 Testing {device.upper()}")
        print("-" * 30)
        
        # Test status
        test_device_status(device)
        time.sleep(0.5)
        
        # Test details
        test_device_details(device)
        time.sleep(0.5)
        
        # Test command (might fail if device is offline)
        test_device_command(device, commands[device])
        time.sleep(0.5)
    
    print("\n🎉 Test suite completed!")
    print("\n📖 Next steps:")
    print("   - Open http://localhost:8080/docs for API documentation")
    print("   - Open your control panel (index.html) in a web browser")
    print("   - Check the API logs for detailed information")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the API server running on http://localhost:8080?")
        print("   Start with: ./start_api.sh")
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
