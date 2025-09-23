# 🛡️ PenTest Master Device API

A FastAPI-based master device API for controlling penetration testing devices through HTTP endpoints while managing MQTT communication with individual devices.

## 🏗️ Architecture

```
Control Panel (Web) <--HTTP--> Master Device API <--MQTT--> Individual Devices
```

- **Control Panel**: Web interface for operators
- **Master Device API**: FastAPI server (this component)  
- **Individual Devices**: Keylogger, Keystroke Injector, Ethernet Tap, Evil Twin AP

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   ./start_api.sh
   ```

2. **Manual Setup**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8080 --reload
   ```

3. **Access**:
   - API Server: http://localhost:8080
   - API Documentation: http://localhost:8080/docs
   - Interactive API: http://localhost:8080/redoc

## 📡 API Endpoints

### Health Check
- `GET /api/health` - Master device health status

### Device Endpoints
Each device has its own endpoint structure:

#### Keylogger (`/keylogger`)
- `POST /keylogger/status` - Get device status
- `POST /keylogger/command` - Send commands
- `POST /keylogger/details` - Get detailed info

#### Keystroke Injector (`/keystroke-injector`)
- `POST /keystroke-injector/status` - Get device status
- `POST /keystroke-injector/command` - Send commands  
- `POST /keystroke-injector/details` - Get detailed info

#### Ethernet Tap (`/ethernet-tap`)
- `POST /ethernet-tap/status` - Get device status
- `POST /ethernet-tap/command` - Send commands
- `POST /ethernet-tap/details` - Get detailed info

#### Evil Twin AP (`/evil-twin`)
- `POST /evil-twin/status` - Get device status
- `POST /evil-twin/command` - Send commands
- `POST /evil-twin/details` - Get detailed info

### File Downloads
- `GET /downloads/{filename}` - Download captured files

### WebSocket
- `WS /ws` - Real-time device status updates

## 🎯 Supported Commands

### Keylogger
- `start_logging` - Begin keystroke capture
- `stop_logging` - Stop keystroke capture  
- `download_logs` - Download captured keystrokes
- `clear_buffer` - Clear keystroke buffer

### Keystroke Injector
- `inject_payload` - Inject keystroke payload
- `load_script` - Load injection script
- `stop_injection` - Stop payload injection
- `list_payloads` - List available payloads

### Ethernet Tap
- `start_capture` - Begin packet capture
- `stop_capture` - Stop packet capture
- `download_pcap` - Download captured packets
- `monitor_mode` - Enable monitor mode

### Evil Twin AP
- `start_ap` - Start rogue access point
- `stop_ap` - Stop rogue access point
- `view_clients` - List connected clients
- `deauth_clients` - Deauthenticate clients
- `clone_network` - Clone existing network

## 📋 Request/Response Examples

### Status Check
```bash
curl -X POST "http://localhost:8080/keylogger/status" \
  -H "Content-Type: application/json" \
  -d '{"device_id": "device1", "timestamp": "2024-09-22T10:30:00Z"}'
```

### Send Command
```bash
curl -X POST "http://localhost:8080/keylogger/command" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "start_logging",
    "parameters": {},
    "device_id": "device1", 
    "timestamp": "2024-09-22T10:30:00Z"
  }'
```

## 🔧 Configuration

Edit `config.json` to customize:
- MQTT broker settings
- Security options
- File storage paths
- Logging configuration

## 🛡️ Security Notes

⚠️ **For authorized penetration testing only**

- Enable authentication in production
- Configure proper CORS origins
- Implement rate limiting
- Use HTTPS in production
- Secure MQTT broker communication

## 📝 Development

### Adding New Devices
1. Add device configuration to `device_data`
2. Create status/command/details endpoints
3. Implement command handler function
4. Add MQTT communication logic

### Testing
```bash
# Run with auto-reload for development
uvicorn main:app --reload --log-level debug

# Test endpoints
python -m pytest tests/
```

## 🚀 Production Deployment

1. **Environment Variables**:
   ```bash
   export API_HOST=0.0.0.0
   export API_PORT=8080
   export MQTT_BROKER=your-mqtt-broker.com
   ```

2. **Docker Deployment**:
   ```dockerfile
   FROM python:3.11-slim
   COPY . /app
   WORKDIR /app
   RUN pip install -r requirements.txt
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
   ```

3. **Reverse Proxy** (nginx/Apache)
4. **SSL/TLS Certificate**
5. **Process Manager** (systemd/supervisor)

## 📊 Monitoring

- Health endpoint: `/api/health`
- Logs: `/tmp/logs/master_device.log`
- Metrics: Built-in FastAPI metrics
- WebSocket: Real-time status updates

## 🤝 Integration

The API is designed to work with:
- Web-based control panels
- Mobile applications
- CLI tools
- Automated testing frameworks
- MQTT-based device networks

---

**⚠️ Legal Disclaimer**: This tool is intended for authorized penetration testing and security research only. Users are responsible for complying with applicable laws and regulations.
