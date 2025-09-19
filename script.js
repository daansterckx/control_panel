// Configuration
const CONFIG = {
    masterDeviceUrl: 'http://192.168.1.10:8080', // Master device endpoint
    updateInterval: 5000, // 5 seconds
    logMaxEntries: 50
};

// Device data storage
let deviceData = {
    router: { id: 'device1', name: 'Router', status: 'offline', ip: '192.168.1.1' },
    nas: { id: 'device2', name: 'NAS Server', status: 'offline', ip: '192.168.1.100' },
    camera: { id: 'device3', name: 'Security Camera', status: 'offline', ip: '192.168.1.201' },
    switch: { id: 'device4', name: 'Smart Switch', status: 'offline', ip: '192.168.1.150' }
};

let vpnStatus = 'disconnected';
let logs = [];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    initializeDeviceMonitoring();
    startPeriodicUpdates();
    addLog('System started', 'info');
});

// Navigation functionality
function initializeNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all links and pages
            navLinks.forEach(l => l.classList.remove('active'));
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            
            // Add active class to clicked link
            this.classList.add('active');
            
            // Show corresponding page
            const pageId = this.getAttribute('data-page');
            const page = document.getElementById(pageId);
            if (page) {
                page.classList.add('active');
            }
        });
    });
}

// Device monitoring and communication
async function checkVpnConnection() {
    try {
        const response = await fetch(`${CONFIG.masterDeviceUrl}/api/vpn/status`, {
            method: 'GET',
            timeout: 3000
        });
        
        if (response.ok) {
            const data = await response.json();
            vpnStatus = data.connected ? 'connected' : 'disconnected';
            updateVpnStatus();
            return true;
        }
    } catch (error) {
        console.error('VPN check failed:', error);
        vpnStatus = 'disconnected';
        updateVpnStatus();
        return false;
    }
}

async function getAllDevicesStatus() {
    try {
        const response = await fetch(`${CONFIG.masterDeviceUrl}/api/devices/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                devices: Object.keys(deviceData)
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            updateDeviceData(data);
            addLog('Device status updated', 'success');
        }
    } catch (error) {
        console.error('Failed to get device status:', error);
        addLog('Failed to update device status', 'error');
    }
}

async function sendDeviceCommand(deviceType, command, parameters = {}) {
    try {
        addLog(`Sending ${command} to ${deviceData[deviceType].name}`, 'info');
        
        const response = await fetch(`${CONFIG.masterDeviceUrl}/api/devices/${deviceType}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: command,
                parameters: parameters,
                timestamp: new Date().toISOString()
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            addLog(`${deviceData[deviceType].name}: ${command} executed successfully`, 'success');
            
            // Refresh device status after command
            setTimeout(() => getAllDevicesStatus(), 1000);
            
            return result;
        } else {
            throw new Error(`Command failed: ${response.statusText}`);
        }
    } catch (error) {
        console.error(`Failed to send command to ${deviceType}:`, error);
        addLog(`${deviceData[deviceType].name}: ${command} failed - ${error.message}`, 'error');
    }
}

async function getDeviceDetails(deviceType) {
    try {
        const response = await fetch(`${CONFIG.masterDeviceUrl}/api/devices/${deviceType}/details`, {
            method: 'GET'
        });
        
        if (response.ok) {
            const details = await response.json();
            updateDeviceDisplay(deviceType, details);
        }
    } catch (error) {
        console.error(`Failed to get ${deviceType} details:`, error);
    }
}

// Update functions
function updateDeviceData(data) {
    Object.keys(data.devices).forEach(deviceType => {
        if (deviceData[deviceType]) {
            Object.assign(deviceData[deviceType], data.devices[deviceType]);
        }
    });
    
    updateOverviewDisplay();
    updateAllDeviceDisplays();
}

function updateVpnStatus() {
    const statusElement = document.getElementById('vpnStatus');
    if (statusElement) {
        statusElement.textContent = vpnStatus === 'connected' ? 'VPN Connected' : 'VPN Disconnected';
        statusElement.className = `connection-status ${vpnStatus === 'connected' ? 'status-connected' : 'status-disconnected'}`;
    }
    
    // Update network info in overview
    const networkStatus = document.querySelector('.network-info .status-text');
    if (networkStatus) {
        networkStatus.textContent = vpnStatus === 'connected' ? 'Connected' : 'Disconnected';
        networkStatus.className = `status-text ${vpnStatus === 'connected' ? 'connected' : 'disconnected'}`;
    }
}

function updateOverviewDisplay() {
    const onlineDevices = Object.values(deviceData).filter(device => device.status === 'online').length;
    const offlineDevices = Object.values(deviceData).length - onlineDevices;
    
    // Update device counts
    const statusSummary = document.querySelector('.status-summary');
    if (statusSummary) {
        statusSummary.innerHTML = `
            <div class="status-item">
                <span class="device-status status-online"></span>
                <span>${onlineDevices} Online</span>
            </div>
            <div class="status-item">
                <span class="device-status status-offline"></span>
                <span>${offlineDevices} Offline</span>
            </div>
        `;
    }
    
    // Update last update time
    const lastUpdate = document.getElementById('lastUpdate');
    if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleTimeString();
    }
}

function updateAllDeviceDisplays() {
    Object.keys(deviceData).forEach(deviceType => {
        const device = deviceData[deviceType];
        const devicePage = document.getElementById(device.id);
        
        if (devicePage) {
            const statusIndicator = devicePage.querySelector('.device-status');
            const buttons = devicePage.querySelectorAll('.btn');
            
            if (statusIndicator) {
                statusIndicator.className = `device-status status-${device.status}`;
            }
            
            // Enable/disable buttons based on device status
            buttons.forEach(button => {
                button.disabled = device.status !== 'online';
            });
        }
    });
}

function updateDeviceDisplay(deviceType, details) {
    const device = deviceData[deviceType];
    const devicePage = document.getElementById(device.id);
    
    if (devicePage && details) {
        const infoSection = devicePage.querySelector('.device-info');
        if (infoSection && details.info) {
            let infoHTML = '';
            Object.entries(details.info).forEach(([key, value]) => {
                infoHTML += `<p>${key}: ${value}</p>`;
            });
            infoSection.innerHTML = infoHTML;
        }
    }
}

// Logging functionality
function addLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = {
        timestamp,
        message,
        type
    };
    
    logs.unshift(logEntry);
    
    // Limit log entries
    if (logs.length > CONFIG.logMaxEntries) {
        logs = logs.slice(0, CONFIG.logMaxEntries);
    }
    
    updateLogsDisplay();
}

function updateLogsDisplay() {
    const logsContainer = document.getElementById('logsContainer');
    if (logsContainer) {
        logsContainer.innerHTML = logs.map(log => `
            <div class="log-entry">
                <span class="log-timestamp">${log.timestamp}</span>
                <span class="log-${log.type}">${log.message}</span>
            </div>
        `).join('');
        
        // Auto-scroll to top for newest logs
        logsContainer.scrollTop = 0;
    }
}

function clearLogs() {
    logs = [];
    updateLogsDisplay();
    addLog('Logs cleared', 'info');
}

// Device control functions
function initializeDeviceMonitoring() {
    // Add click handlers for device control buttons
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn') && !e.target.disabled) {
            const devicePage = e.target.closest('.page');
            if (devicePage) {
                const deviceType = getDeviceTypeFromPageId(devicePage.id);
                const command = getCommandFromButton(e.target);
                
                if (deviceType && command) {
                    sendDeviceCommand(deviceType, command);
                }
            }
        }
    });
}

function getDeviceTypeFromPageId(pageId) {
    const deviceMap = {
        'device1': 'router',
        'device2': 'nas',
        'device3': 'camera',
        'device4': 'switch'
    };
    return deviceMap[pageId];
}

function getCommandFromButton(button) {
    const buttonText = button.textContent.toLowerCase().trim();
    const commandMap = {
        'reboot': 'reboot',
        'reset config': 'reset_config',
        'shutdown': 'shutdown',
        'backup now': 'backup',
        'check health': 'health_check',
        'view live': 'view_live',
        'start recording': 'start_recording',
        'disable': 'disable',
        'reconnect': 'reconnect',
        'port config': 'port_config',
        'reset': 'reset'
    };
    return commandMap[buttonText];
}

// Periodic updates
function startPeriodicUpdates() {
    // Initial check
    checkVpnConnection().then(vpnOk => {
        if (vpnOk) {
            getAllDevicesStatus();
        }
    });
    
    // Set up periodic updates
    setInterval(async () => {
        const vpnOk = await checkVpnConnection();
        if (vpnOk) {
            getAllDevicesStatus();
        }
        
        // Update latency simulation (replace with actual ping later)
        updateLatencyDisplay();
    }, CONFIG.updateInterval);
}

function updateLatencyDisplay() {
    const latencyElement = document.getElementById('latency');
    if (latencyElement && vpnStatus === 'connected') {
        // Simulate latency - replace with actual ping to master device
        const latency = Math.floor(Math.random() * 50) + 30;
        latencyElement.textContent = `${latency}ms`;
    } else if (latencyElement) {
        latencyElement.textContent = 'N/A';
    }
}

// Utility functions
function showNotification(message, type = 'info') {
    // Simple notification - you can enhance this with a proper notification system
    console.log(`[${type.toUpperCase()}] ${message}`);
    addLog(message, type);
}

// Export functions for global access
window.clearLogs = clearLogs;
window.sendDeviceCommand = sendDeviceCommand;
window.getDeviceDetails = getDeviceDetails;