// Configuration
const CONFIG = {
    masterDeviceUrl: 'http://localhost:8080', // Master device endpoint (FastAPI server)
    updateInterval: 5000, // 5 seconds
    logMaxEntries: 100,
    authToken: null, // Authentication token if needed
    timeout: 10000 // Request timeout in milliseconds
};

// Penetration testing device configuration with master device endpoints
let deviceData = {
    keylogger: { 
        id: 'device1', 
        name: 'Keylogger', 
        status: 'offline', 
        endpoint: '/keylogger',
        type: 'keylogger',
        instances: [],
        lastSeen: null,
        capabilities: ['start_logging', 'stop_logging', 'download_logs', 'clear_buffer']
    },
    keystroke_injector: { 
        id: 'device2', 
        name: 'Keystroke Injector', 
        status: 'offline', 
        endpoint: '/keystroke-injector',
        type: 'keystroke_injector',
        instances: [],
        lastSeen: null,
        capabilities: ['inject_payload', 'load_script', 'stop_injection', 'list_payloads']
    },
    ethernet_tap: { 
        id: 'device3', 
        name: 'Ethernet Tap', 
        status: 'offline', 
        endpoint: '/ethernet-tap',
        type: 'ethernet_tap',
        instances: [],
        lastSeen: null,
        capabilities: ['start_capture', 'stop_capture', 'download_pcap', 'monitor_mode']
    },
    evil_twin: { 
        id: 'device4', 
        name: 'Evil Twin AP', 
        status: 'offline', 
        endpoint: '/evil-twin',
        type: 'evil_twin',
        instances: [],
        lastSeen: null,
        capabilities: ['start_ap', 'stop_ap', 'view_clients', 'deauth_clients', 'clone_network']
    }
};

let masterStatus = 'disconnected';
let logs = [];
let updateTimer = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApplication();
});

function initializeApplication() {
    addLog('PenTest Control Panel initializing...', 'info');
    
    initializeNavigation();
    initializeEventHandlers();
    
    // Start with initial master device connection check
    checkMasterConnection().then(() => {
        startPeriodicUpdates();
    });
    
    addLog('Control panel ready for deployment', 'success');
}

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
            
            // Show corresponding page with animation
            const pageId = this.getAttribute('data-page');
            const page = document.getElementById(pageId);
            if (page) {
                page.classList.add('active');
                
                // Load device details if it's a device page
                if (pageId !== 'overview') {
                    const deviceType = getDeviceTypeFromPageId(pageId);
                    if (deviceType && deviceData[deviceType].status === 'online') {
                        loadDeviceDetails(deviceType);
                    }
                }
            }
        });
    });
}

// Master device communication functions
async function checkMasterConnection() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.timeout);
        
        const response = await fetch(`${CONFIG.masterDeviceUrl}/api/health`, {
            method: 'GET',
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                ...(CONFIG.authToken && { 'Authorization': `Bearer ${CONFIG.authToken}` })
            }
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            const data = await response.json();
            masterStatus = 'connected';
            updateMasterStatus();
            addLog('Master device connection established', 'success');
            return true;
        } else {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
    } catch (error) {
        console.error('Master connection failed:', error);
        masterStatus = 'disconnected';
        updateMasterStatus();
        addLog(`Master device connection failed: ${error.message}`, 'error');
        return false;
    }
}

async function getAllDevicesStatus() {
    if (masterStatus !== 'connected') {
        return false;
    }
    
    try {
        // Get status from each device endpoint individually
        const statusPromises = Object.entries(deviceData).map(async ([deviceType, device]) => {
            try {
                const response = await fetch(`${CONFIG.masterDeviceUrl}${device.endpoint}/status`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(CONFIG.authToken && { 'Authorization': `Bearer ${CONFIG.authToken}` })
                    },
                    body: JSON.stringify({
                        device_id: device.id,
                        timestamp: new Date().toISOString()
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    return { deviceType, status: data, success: true };
                } else {
                    return { deviceType, status: { status: 'offline', error: response.statusText }, success: false };
                }
            } catch (error) {
                return { deviceType, status: { status: 'offline', error: error.message }, success: false };
            }
        });
        
        const results = await Promise.all(statusPromises);
        
        // Update device data with results
        results.forEach(({ deviceType, status, success }) => {
            if (deviceData[deviceType]) {
                const oldStatus = deviceData[deviceType].status;
                
                // Update device data
                deviceData[deviceType].status = status.status || 'offline';
                deviceData[deviceType].lastSeen = status.last_seen || deviceData[deviceType].lastSeen;
                deviceData[deviceType].instances = status.instances || [];
                
                // Log status changes
                if (oldStatus !== deviceData[deviceType].status) {
                    addLog(`${deviceData[deviceType].name}: Status changed from ${oldStatus} to ${deviceData[deviceType].status}`, 
                           deviceData[deviceType].status === 'online' ? 'success' : 'warning');
                }
                
                // Update additional device info if provided
                if (status.device_info) {
                    Object.assign(deviceData[deviceType], status.device_info);
                }
            }
        });
        
        updateOverviewDisplay();
        updateAllDeviceDisplays();
        
        return true;
    } catch (error) {
        console.error('Failed to get devices status:', error);
        addLog('Failed to update device status', 'error');
        return false;
    }
}

async function sendDeviceCommand(deviceType, command, parameters = {}) {
    if (masterStatus !== 'connected') {
        addLog('Cannot send command: Master device not connected', 'error');
        showNotification('Master device not connected', 'error');
        return false;
    }
    
    const device = deviceData[deviceType];
    if (!device) {
        addLog(`Unknown device type: ${deviceType}`, 'error');
        return false;
    }
    
    // Check if device is online for most commands
    if (device.status !== 'online' && !['refresh', 'reconnect'].includes(command)) {
        addLog(`Cannot send ${command} to ${device.name}: Device is offline`, 'warning');
        showNotification(`${device.name} is offline`, 'warning');
        return false;
    }
    
    try {
        addLog(`Sending ${command} command to ${device.name}`, 'info');
        
        // Add loading state to device card
        const devicePage = document.getElementById(device.id);
        if (devicePage) {
            devicePage.classList.add('loading');
        }
        
        const response = await fetch(`${CONFIG.masterDeviceUrl}${device.endpoint}/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(CONFIG.authToken && { 'Authorization': `Bearer ${CONFIG.authToken}` })
            },
            body: JSON.stringify({
                command: command,
                parameters: parameters,
                device_id: device.id,
                timestamp: new Date().toISOString()
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            addLog(`${device.name}: ${command} executed successfully`, 'success');
            showNotification(`${command} sent to ${device.name}`, 'success');
            
            // Handle command-specific responses
            handleCommandResponse(deviceType, command, result);
            
            // Refresh device status after command
            setTimeout(() => refreshSingleDevice(deviceType), 1000);
            
            return result;
        } else {
            throw new Error(result.error || `Command failed: ${response.statusText}`);
        }
    } catch (error) {
        console.error(`Failed to send command to ${deviceType}:`, error);
        addLog(`${device.name}: ${command} failed - ${error.message}`, 'error');
        showNotification(`Command failed: ${error.message}`, 'error');
        return false;
    } finally {
        // Remove loading state
        const devicePage = document.getElementById(device.id);
        if (devicePage) {
            devicePage.classList.remove('loading');
        }
    }
}

async function loadDeviceDetails(deviceType) {
    const device = deviceData[deviceType];
    if (!device || device.status !== 'online') {
        return false;
    }
    
    try {
        const response = await fetch(`${CONFIG.masterDeviceUrl}${device.endpoint}/details`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(CONFIG.authToken && { 'Authorization': `Bearer ${CONFIG.authToken}` })
            },
            body: JSON.stringify({
                device_id: device.id,
                include_instances: true
            })
        });
        
        if (response.ok) {
            const details = await response.json();
            updateDeviceDisplay(deviceType, details);
            return true;
        }
    } catch (error) {
        console.error(`Failed to load ${deviceType} details:`, error);
        return false;
    }
}

async function refreshSingleDevice(deviceType) {
    const device = deviceData[deviceType];
    if (!device) return false;
    
    try {
        const response = await fetch(`${CONFIG.masterDeviceUrl}${device.endpoint}/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(CONFIG.authToken && { 'Authorization': `Bearer ${CONFIG.authToken}` })
            },
            body: JSON.stringify({
                device_id: device.id,
                timestamp: new Date().toISOString()
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            
            const oldStatus = device.status;
            device.status = data.status || 'offline';
            device.lastSeen = data.last_seen || device.lastSeen;
            device.instances = data.instances || [];
            
            if (oldStatus !== device.status) {
                addLog(`${device.name}: Status updated to ${device.status}`, 
                       device.status === 'online' ? 'success' : 'warning');
            }
            
            updateOverviewDisplay();
            updateSingleDeviceDisplay(deviceType);
            return true;
        }
    } catch (error) {
        console.error(`Failed to refresh ${deviceType}:`, error);
        return false;
    }
}

// Update functions
function updateMasterStatus() {
    // Update master device status in overview
    const masterStatusElement = document.getElementById('masterStatus');
    if (masterStatusElement) {
        masterStatusElement.textContent = masterStatus === 'connected' ? 'Connected' : 'Disconnected';
        masterStatusElement.className = `status-text ${masterStatus === 'connected' ? 'connected' : 'disconnected'}`;
    }
    
    // Update VPN status indicator (master connection = VPN status)
    const vpnStatusElement = document.getElementById('vpnStatus');
    if (vpnStatusElement) {
        const isConnected = masterStatus === 'connected';
        vpnStatusElement.textContent = isConnected ? 'Master Connected' : 'Master Disconnected';
        vpnStatusElement.className = `connection-status ${isConnected ? 'status-connected' : 'status-disconnected'}`;
    }
    
    // Update network status
    const networkStatus = document.querySelector('.network-info .status-text');
    if (networkStatus) {
        networkStatus.textContent = masterStatus === 'connected' ? 'Connected' : 'Disconnected';
        networkStatus.className = `status-text ${masterStatus === 'connected' ? 'connected' : 'disconnected'}`;
    }
}

function updateOverviewDisplay() {
    const onlineDevices = Object.values(deviceData).filter(device => device.status === 'online').length;
    const offlineDevices = Object.values(deviceData).length - onlineDevices;
    
    // Count total instances across all devices
    const totalInstances = Object.values(deviceData).reduce((total, device) => {
        return total + (device.instances ? device.instances.length : 0);
    }, 0);
    
    const activeInstances = Object.values(deviceData).reduce((total, device) => {
        if (!device.instances) return total;
        return total + device.instances.filter(instance => 
            instance.status === 'running' || instance.status === 'active'
        ).length;
    }, 0);
    
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
    
    // Update system info
    const systemInfo = document.querySelector('.system-info');
    if (systemInfo) {
        systemInfo.innerHTML = `
            <p>Master Device: <span id="masterStatus" class="status-text ${masterStatus === 'connected' ? 'connected' : 'disconnected'}">${masterStatus === 'connected' ? 'Connected' : 'Disconnected'}</span></p>
            <p>Auto-Update: <span>Every ${CONFIG.updateInterval / 1000} seconds</span></p>
            <p>Active Instances: <span>${activeInstances}/${totalInstances}</span></p>
        `;
    }
    
    // Update last update time
    const lastUpdate = document.getElementById('lastUpdate');
    if (lastUpdate) {
        lastUpdate.textContent = new Date().toLocaleTimeString();
    }
    
    // Update latency
    updateLatencyDisplay();
}

function updateAllDeviceDisplays() {
    Object.keys(deviceData).forEach(deviceType => {
        updateSingleDeviceDisplay(deviceType);
    });
}

function updateSingleDeviceDisplay(deviceType) {
    const device = deviceData[deviceType];
    const devicePage = document.getElementById(device.id);
    
    if (!devicePage) return;
    
    // Update status indicator
    const statusIndicator = devicePage.querySelector('.device-status');
    if (statusIndicator) {
        statusIndicator.className = `device-status status-${device.status}`;
    }
    
    // Update device info
    const deviceInfo = devicePage.querySelector('.device-info');
    if (deviceInfo) {
        const instanceCount = device.instances ? device.instances.length : 0;
        const activeCount = device.instances ? 
            device.instances.filter(i => i.status === 'running' || i.status === 'active').length : 0;
        
        deviceInfo.innerHTML = `
            <p>Endpoint: <span>${device.endpoint}</span></p>
            <p>Status: <span class="status-text ${device.status === 'online' ? 'connected' : 'disconnected'}">${device.status}</span></p>
            <p>Instances: <span>${activeCount}/${instanceCount}</span></p>
            <p>Last Seen: <span>${device.lastSeen || 'Never'}</span></p>
        `;
    }
    
    // Enable/disable buttons based on device status
    const buttons = devicePage.querySelectorAll('.btn:not(.instance-btn)');
    buttons.forEach(button => {
        button.disabled = device.status !== 'online';
    });
    
    // Update instances display
    updateInstancesDisplay(devicePage, device);
}

function updateInstancesDisplay(devicePage, device) {
    const instancesContainer = devicePage.querySelector('.instances-container');
    if (!instancesContainer || !device.instances) {
        return;
    }
    
    if (device.instances.length === 0) {
        instancesContainer.innerHTML = '<p class="no-instances">No active instances</p>';
        return;
    }
    
    instancesContainer.innerHTML = device.instances.map(instance => `
        <div class="instance-item">
            <div class="instance-info">
                <span class="instance-name">${instance.name || instance.id}</span>
                <span class="instance-status status-${instance.status}">${instance.status}</span>
            </div>
            <div class="instance-details">
                ${instance.details ? `<small>${instance.details}</small>` : ''}
            </div>
            <div class="instance-controls">
                <button class="btn btn-small instance-btn" 
                        onclick="controlInstance('${device.type}', '${instance.id}', 'start')" 
                        ${instance.status === 'running' || instance.status === 'active' ? 'disabled' : ''}>
                    Start
                </button>
                <button class="btn btn-small btn-danger instance-btn" 
                        onclick="controlInstance('${device.type}', '${instance.id}', 'stop')" 
                        ${instance.status === 'stopped' || instance.status === 'inactive' ? 'disabled' : ''}>
                    Stop
                </button>
                <button class="btn btn-small instance-btn" 
                        onclick="controlInstance('${device.type}', '${instance.id}', 'remove')">
                    Remove
                </button>
            </div>
        </div>
    `).join('');
}

function updateDeviceDisplay(deviceType, details) {
    const device = deviceData[deviceType];
    const devicePage = document.getElementById(device.id);
    
    if (devicePage && details) {
        // Update additional device information
        if (details.device_info) {
            Object.assign(device, details.device_info);
        }
        
        // Update instances
        if (details.instances) {
            device.instances = details.instances;
        }
        
        // Refresh the display
        updateSingleDeviceDisplay(deviceType);
    }
}

// Event handlers
function initializeEventHandlers() {
    // Add click handlers for device control buttons
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn') && !e.target.disabled && !e.target.onclick) {
            const devicePage = e.target.closest('.page');
            if (devicePage && devicePage.id !== 'overview') {
                const deviceType = getDeviceTypeFromPageId(devicePage.id);
                const command = getCommandFromButton(e.target);
                
                if (deviceType && command) {
                    sendDeviceCommand(deviceType, command);
                }
            }
        }
    });
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case '1':
                    e.preventDefault();
                    document.querySelector('[data-page="overview"]').click();
                    break;
                case '2':
                    e.preventDefault();
                    document.querySelector('[data-page="device1"]').click();
                    break;
                case '3':
                    e.preventDefault();
                    document.querySelector('[data-page="device2"]').click();
                    break;
                case '4':
                    e.preventDefault();
                    document.querySelector('[data-page="device3"]').click();
                    break;
                case '5':
                    e.preventDefault();
                    document.querySelector('[data-page="device4"]').click();
                    break;
            }
        }
    });
}

async function controlInstance(deviceType, instanceId, action) {
    const parameters = { instanceId: instanceId, action: action };
    await sendDeviceCommand(deviceType, 'control_instance', parameters);
}

function getDeviceTypeFromPageId(pageId) {
    const deviceMap = {
        'device1': 'keylogger',
        'device2': 'keystroke_injector',
        'device3': 'ethernet_tap',
        'device4': 'evil_twin'
    };
    return deviceMap[pageId];
}

function getCommandFromButton(button) {
    const buttonText = button.textContent.toLowerCase().trim();
    const commandMap = {
        // Keylogger commands
        'start logging': 'start_logging',
        'stop logging': 'stop_logging',
        'download logs': 'download_logs',
        'clear buffer': 'clear_buffer',
        
        // Keystroke Injector commands
        'inject payload': 'inject_payload',
        'load script': 'load_script',
        'stop injection': 'stop_injection',
        'list payloads': 'list_payloads',
        
        // Ethernet Tap commands
        'start capture': 'start_capture',
        'stop capture': 'stop_capture',
        'download pcap': 'download_pcap',
        'monitor mode': 'monitor_mode',
        
        // Evil Twin AP commands
        'start ap': 'start_ap',
        'stop ap': 'stop_ap',
        'view clients': 'view_clients',
        'deauth clients': 'deauth_clients',
        'clone network': 'clone_network',
        
        // Common commands
        'shutdown': 'shutdown',
        'restart': 'restart',
        'status': 'get_status',
        'refresh': 'refresh'
    };
    return commandMap[buttonText];
}

function handleCommandResponse(deviceType, command, result) {
    const device = deviceData[deviceType];
    
    // Handle specific command responses
    switch(command) {
        case 'download_logs':
        case 'download_pcap':
            if (result.download_url) {
                // Create download link
                const link = document.createElement('a');
                link.href = result.download_url;
                link.download = result.filename || 'download';
                link.click();
                addLog(`${device.name}: Download started`, 'success');
            }
            break;
            
        case 'view_clients':
            if (result.clients) {
                addLog(`${device.name}: ${result.clients.length} clients connected`, 'info');
            }
            break;
            
        case 'list_payloads':
            if (result.payloads) {
                addLog(`${device.name}: ${result.payloads.length} payloads available`, 'info');
            }
            break;
    }
}

// Logging functionality
function addLog(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = {
        timestamp,
        message,
        type,
        id: Date.now() + Math.random()
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
        if (logs.length === 0) {
            logsContainer.innerHTML = '<div class="log-entry"><span class="log-info">No logs available</span></div>';
            return;
        }
        
        logsContainer.innerHTML = logs.map(log => `
            <div class="log-entry" data-log-id="${log.id}">
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
    addLog('Logs cleared by user', 'info');
}

// Periodic updates
function startPeriodicUpdates() {
    // Clear any existing timer
    if (updateTimer) {
        clearInterval(updateTimer);
    }
    
    // Set up periodic updates
    updateTimer = setInterval(async () => {
        const masterConnected = await checkMasterConnection();
        
        if (masterConnected) {
            await getAllDevicesStatus();
        }
    }, CONFIG.updateInterval);
    
    addLog(`Periodic updates started (${CONFIG.updateInterval / 1000}s interval)`, 'info');
}

function stopPeriodicUpdates() {
    if (updateTimer) {
        clearInterval(updateTimer);
        updateTimer = null;
        addLog('Periodic updates stopped', 'warning');
    }
}

function updateLatencyDisplay() {
    const latencyElement = document.getElementById('latency');
    if (latencyElement) {
        if (masterStatus === 'connected') {
            // Simulate realistic latency - replace with actual ping measurement
            const baseLatency = 25;
            const variance = 15;
            const latency = Math.floor(baseLatency + (Math.random() * variance));
            latencyElement.textContent = `${latency}ms`;
        } else {
            latencyElement.textContent = 'N/A';
        }
    }
}

// Utility functions
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
    
    addLog(message, type);
}

// Export functions for global access
window.clearLogs = clearLogs;
window.sendDeviceCommand = sendDeviceCommand;
window.loadDeviceDetails = loadDeviceDetails;
window.controlInstance = controlInstance;
window.stopPeriodicUpdates = stopPeriodicUpdates;
window.startPeriodicUpdates = startPeriodicUpdates;

// Handle page unload
window.addEventListener('beforeunload', function() {
    stopPeriodicUpdates();
});
