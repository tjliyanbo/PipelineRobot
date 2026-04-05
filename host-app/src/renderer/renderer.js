// State Management
const state = {
    connected: false,
    videoEnabled: false,
    videoFit: localStorage.getItem('video-fit') || 'contain', // 'contain' or 'fill'
    lightEnabled: false,
    move: { speed: 0, turn: 0 }
};

// DOM Elements
const elements = {
    statusDot: document.getElementById('status-dot'),
    statusText: document.getElementById('status-text'),
    btnConnect: document.getElementById('btn-connect'),
    videoContainer: document.getElementById('video-container'),
    btnVideoToggle: document.getElementById('btn-video-toggle'),
    btnVideoAspect: document.getElementById('btn-video-aspect'),
    btnRealPhoto: document.getElementById('btn-real-photo'),
    btnSnapshot: document.getElementById('btn-snapshot'),
    btnRecord: document.getElementById('btn-record'),
    videoFeed: document.getElementById('video-feed'),
    videoPlaceholder: document.getElementById('video-placeholder'),
    btnLight: document.getElementById('btn-light'),
    logContainer: document.getElementById('log-container'),
    sensors: {
        temp: document.getElementById('val-temp'),
        pressure: document.getElementById('val-pressure'),
        battery: document.getElementById('val-battery'),
        humidity: document.getElementById('val-humidity')
    },
    controls: {
        forward: document.getElementById('btn-forward'),
        backward: document.getElementById('btn-backward'),
        left: document.getElementById('btn-left'),
        right: document.getElementById('btn-right'),
        reset: document.getElementById('btn-reset')
    }
};

// Helper Functions
function log(msg, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    
    // Map type to class
    let className = 'log-entry';
    if (type === 'success') className += ' log-success';
    else if (type === 'warning') className += ' log-warning';
    else if (type === 'error') className += ' log-error';
    else className += ' log-info';
    
    entry.className = className;
    entry.innerHTML = `<span class="log-time">${time}</span> ${msg}`;
    elements.logContainer.prepend(entry);
}

function updateConnectionUI(status) {
    state.connected = status === 'Connected';
    
    if (state.connected) {
        elements.statusDot.classList.add('connected');
        elements.statusText.innerText = "已在线";
        elements.statusText.style.color = "var(--success-color)";
        elements.btnConnect.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z" /></svg> 断开';
        log("系统已连接", "success");
    } else {
        elements.statusDot.classList.remove('connected');
        elements.statusText.innerText = "离线";
        elements.statusText.style.color = "#888";
        elements.btnConnect.innerHTML = '<svg class="icon" viewBox="0 0 24 24"><path d="M19,15H13V3H19M11,15H5V3H11M21,3H3A2,2 0 0,0 1,5V19A2,2 0 0,0 3,21H21A2,2 0 0,0 23,19V5A2,2 0 0,0 21,3Z" /></svg> 连接';
        log("系统已断开", "warning");
    }
}

function updateVideoUI() {
    const btn = elements.btnVideoToggle;
    const container = document.getElementById('video-container'); // Need reference to container for hover effect

    if (state.videoEnabled) {
        elements.videoFeed.style.display = 'block';
        elements.videoPlaceholder.style.display = 'none';
        
        // Update Button Text & Icon for "Close"
        btn.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24"><path d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z" /></svg>
            <span>关闭视频 (Esc)</span>
        `;
        btn.setAttribute('aria-label', 'Close Video Stream');
        btn.classList.add('btn-danger'); // Optional: Red style for close? No, stick to overlay style.
        
        // Add class to container to enable hover-only visibility
        container.classList.add('video-playing');

    } else {
        elements.videoFeed.style.display = 'none';
        elements.videoFeed.src = "";
        elements.videoPlaceholder.style.display = 'flex';
        
        // Update Button Text & Icon for "Open"
        btn.innerHTML = `
            <svg class="icon" viewBox="0 0 24 24"><path d="M8,5.14V19.14L19,12.14L8,5.14Z" /></svg>
            <span>开启视频</span>
        `;
        btn.setAttribute('aria-label', 'Open Video Stream');
        btn.classList.remove('btn-danger');
        
        // Remove class to make button always visible
        container.classList.remove('video-playing');
    }
}

function updateAspectRatioUI() {
    const isFill = state.videoFit === 'fill';
    elements.videoFeed.style.objectFit = state.videoFit;
    
    // Save preference
    localStorage.setItem('video-fit', state.videoFit);
    
    // Update Icon & Title
    // If currently Fill, show icon to switch to Fit (arrows pointing in)
    // If currently Fit, show icon to switch to Fill (arrows pointing out)
    const iconPath = isFill 
        ? "M5,16H8V19H11V16H14V13H11V10H8V13H5V16M19,5H5C3.89,5 3,5.89 3,7V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V7A2,2 0 0,0 19,5Z" // Center Focus / Fit
        : "M19,12H17V15H14V17H19V12M7,9H5V12H2V14H5V17H7V14H10V12H7V9M19,3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3Z"; // Expand / Fill

    elements.btnVideoAspect.innerHTML = `<svg viewBox="0 0 24 24"><path d="${iconPath}" /></svg>`;
    elements.btnVideoAspect.title = isFill ? "切换到适应 (Fit)" : "切换到填充 (Fill)";
}

// Global Key Listener for Esc
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.videoEnabled) {
        toggleVideo();
    }
});

// Communication Handlers
window.api.onStatus((status) => {
    updateConnectionUI(status);
});

window.api.onTelemetry((data) => {
    // Check for validity before updating to avoid NaN flashing
    if (data.temperature !== undefined) elements.sensors.temp.innerText = data.temperature.toFixed(1);
    if (data.pressure !== undefined) elements.sensors.pressure.innerText = data.pressure.toFixed(1);
    if (data.battery !== undefined) elements.sensors.battery.innerText = data.battery.toFixed(1);
    if (data.humidity !== undefined) elements.sensors.humidity.innerText = data.humidity.toFixed(1);
});

window.api.onVideoFrame((base64Img) => {
    // Auto-enable video UI if we are receiving frames
    if (!state.videoEnabled) {
        state.videoEnabled = true;
        updateVideoUI();
    }
    
    elements.videoFeed.src = `data:image/jpeg;base64,${base64Img}`;
});

// User Actions
function toggleConnect() {
    if (state.connected) {
        window.api.disconnect();
    } else {
        window.api.connect();
    }
}

function toggleVideo() {
    state.videoEnabled = !state.videoEnabled;
    updateVideoUI();
    
    window.api.setVideo(state.videoEnabled)
        .then(() => log(state.videoEnabled ? "视频流已开启" : "视频流已关闭", "info"))
        .catch(err => log(`视频指令错误: ${err}`, "error"));
}

function emergencyStop() {
    log("!!! 紧急停止触发 !!!", "error");
    sendControlCommand(0, 0);
    // Send reset as well just in case? No, Estop should just kill power/movement.
}

function sendControlCommand(speed, turn) {
    state.move = { speed, turn };
    window.api.sendControl({ ...state.move, light: state.lightEnabled });
    // Don't spam logs with movement commands unless it's a state change or important
    // log(`发送指令: Speed=${speed}, Turn=${turn}`); 
}

function sendResetCommand() {
    // Reset Yaw
    window.api.sendControl({ reset_yaw: true, speed: 0, turn: 0, light: state.lightEnabled });
    state.move = { speed: 0, turn: 0 }; // Ensure local state matches
    log("发送指令: 复位 (Reset Yaw)", "warning");
}

// Control Bindings
// We use mousedown/mouseup for press-and-hold behavior, and touch events for mobile support

function setupButton(btn, speed, turn) {
    const start = (e) => {
        e.preventDefault(); // Prevent text selection
        if (!state.connected) return;
        btn.classList.add('active');
        sendControlCommand(speed, turn);
    };

    const end = (e) => {
        e.preventDefault();
        if (!state.connected) return;
        btn.classList.remove('active');
        sendControlCommand(0, 0);
    };

    btn.addEventListener('mousedown', start);
    btn.addEventListener('mouseup', end);
    btn.addEventListener('mouseleave', end); // Handle dragging mouse out

    btn.addEventListener('touchstart', start);
    btn.addEventListener('touchend', end);
}

// Bind D-Pad
// Reduced speed to 0.5 (was 1.0) for smoother control
setupButton(elements.controls.forward, 0.5, 0.0);
setupButton(elements.controls.backward, -0.5, 0.0);
setupButton(elements.controls.left, 0.0, 1.0);  // Left turns CCW (Positive Yaw)
setupButton(elements.controls.right, 0.0, -1.0);  // Right turns CW (Negative Yaw)

// Reset Button
elements.controls.reset.addEventListener('click', () => {
    if (!state.connected) return;
    sendResetCommand();
});

// Event Listeners
elements.btnConnect.addEventListener('click', toggleConnect);
elements.btnVideoToggle.addEventListener('click', toggleVideo);
elements.btnVideoAspect.addEventListener('click', toggleAspectRatio);
elements.btnRealPhoto.addEventListener('click', () => {
    window.api.toggleRealPhoto();
    log("切换显示模式 (真实/CG)", "info");
});
elements.btnSnapshot.addEventListener('click', () => {
    window.api.takeSnapshot();
    log("发送截图指令", "success");
});
elements.btnRecord.addEventListener('click', () => {
    window.api.toggleRecording();
    elements.btnRecord.classList.toggle('recording');
    const isRecording = elements.btnRecord.classList.contains('recording');
    log(isRecording ? "开始录制" : "停止录制", isRecording ? "warning" : "success");
});

function toggleAspectRatio() {
    state.videoFit = state.videoFit === 'contain' ? 'fill' : 'contain';
    localStorage.setItem('videoFit', state.videoFit);
    updateAspectRatioUI();
}

function updateAspectRatioUI() {
    elements.videoFeed.style.objectFit = state.videoFit;
    
    // Update Icon
    if (state.videoFit === 'fill') {
        // Show "Shrink/Fit" icon
        elements.btnVideoAspect.innerHTML = '<svg class="icon" viewBox="0 0 24 24" style="margin:0"><path d="M5,16H8V19H10V14H5V16M16,19H19V16H16V19M14,5V10H19V8H16V5H14M8,5V8H5V10H10V5H8Z" /></svg>';
        elements.btnVideoAspect.title = "切换至保持比例模式";
    } else {
        // Show "Expand/Fill" icon
        elements.btnVideoAspect.innerHTML = '<svg class="icon" viewBox="0 0 24 24" style="margin:0"><path d="M5,5H10V7H7V10H5V5M14,5H19V10H17V7H14V5M17,14H19V19H14V17H17V14M10,17H7V14H5V19H10V17Z" /></svg>';
        elements.btnVideoAspect.title = "切换至拉伸填充模式";
    }
}

// Initial Call
updateAspectRatioUI();

elements.btnLight.addEventListener('click', () => {
    state.lightEnabled = !state.lightEnabled;
    elements.btnLight.classList.toggle('active', state.lightEnabled);
    log(`照明已${state.lightEnabled ? '开启' : '关闭'}`, "info");
    // Send updated light state immediately
    window.api.sendControl({ ...state.move, light: state.lightEnabled });
});

// Initial Log
updateAspectRatioUI(); // Apply saved preference
log("系统就绪，等待连接...", "success");
