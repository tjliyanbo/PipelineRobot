// State Management
const state = {
    connected: false,
    videoEnabled: false,
    lightEnabled: false,
    move: { speed: 0, turn: 0 }
};

// DOM Elements
const elements = {
    statusDot: document.getElementById('status-dot'),
    statusText: document.getElementById('status-text'),
    btnConnect: document.getElementById('btn-connect'),
    btnEstop: document.getElementById('btn-estop'),
    btnVideoToggle: document.getElementById('btn-video-toggle'),
    videoFeed: document.getElementById('video-feed'),
    videoPlaceholder: document.getElementById('video-placeholder'),
    btnLight: document.getElementById('btn-light'),
    logContainer: document.getElementById('log-container'),
    sensors: {
        temp: document.getElementById('val-temp'),
        pressure: document.getElementById('val-pressure'),
        battery: document.getElementById('val-battery'),
        pitch: document.getElementById('val-pitch')
    },
    controls: {
        forward: document.getElementById('btn-forward'),
        backward: document.getElementById('btn-backward'),
        left: document.getElementById('btn-left'),
        right: document.getElementById('btn-right'),
        stop: document.getElementById('btn-stop-move')
    }
};

// Helper Functions
function log(msg) {
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">${time}</span> ${msg}`;
    elements.logContainer.prepend(entry); // Newest on top? Design didn't specify, but prepend is often better for monitoring
    // Or append and scroll
    // elements.logContainer.appendChild(entry);
    // elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
}

function updateConnectionUI(status) {
    state.connected = status === 'Connected';
    
    if (state.connected) {
        elements.statusDot.classList.add('connected');
        elements.statusText.innerText = "已在线";
        elements.statusText.style.color = "var(--success-color)";
        elements.btnConnect.innerText = "断开";
    } else {
        elements.statusDot.classList.remove('connected');
        elements.statusText.innerText = "离线";
        elements.statusText.style.color = "#888";
        elements.btnConnect.innerText = "连接";
        
        // Independent Link: Do NOT auto-disable video on TCP disconnect
        // if (state.videoEnabled) {
        //     toggleVideo(); 
        // }
    }
}

function updateVideoUI() {
    if (state.videoEnabled) {
        elements.videoFeed.style.display = 'block';
        elements.videoPlaceholder.style.display = 'none';
        elements.btnVideoToggle.innerText = "关闭视频";
        elements.btnVideoToggle.style.background = "rgba(255, 0, 0, 0.6)";
    } else {
        elements.videoFeed.style.display = 'none';
        elements.videoFeed.src = "";
        elements.videoPlaceholder.style.display = 'flex';
        elements.btnVideoToggle.innerText = "开启视频";
        elements.btnVideoToggle.style.background = "rgba(0, 0, 0, 0.6)";
    }
}

// Communication Handlers
window.api.onStatus((status) => {
    log(`连接状态更新: ${status}`);
    updateConnectionUI(status);
});

window.api.onTelemetry((data) => {
    // Check for validity before updating to avoid NaN flashing
    if (data.temperature !== undefined) elements.sensors.temp.innerText = data.temperature.toFixed(1);
    if (data.pressure !== undefined) elements.sensors.pressure.innerText = data.pressure.toFixed(1);
    if (data.battery !== undefined) elements.sensors.battery.innerText = data.battery.toFixed(1);
    if (data.pitch !== undefined) elements.sensors.pitch.innerText = data.pitch.toFixed(1);
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
        .then(() => log(state.videoEnabled ? "视频流已开启" : "视频流已关闭"))
        .catch(err => log(`视频指令错误: ${err}`));
}

function emergencyStop() {
    log("!!! 紧急停止触发 !!!");
    sendControlCommand(0, 0);
    // Additional logic could go here (e.g., visual alarm)
}

function sendControlCommand(speed, turn) {
    state.move = { speed, turn };
    window.api.sendControl({ ...state.move, light: state.lightEnabled });
    log(`发送指令: Speed=${speed}, Turn=${turn}`);
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
setupButton(elements.controls.forward, 1.0, 0.0);
setupButton(elements.controls.backward, -1.0, 0.0);
setupButton(elements.controls.left, 0.0, -1.0);
setupButton(elements.controls.right, 0.0, 1.0);

// Stop button (explicit stop)
elements.controls.stop.addEventListener('click', () => {
    sendControlCommand(0, 0);
});

// Event Listeners
elements.btnConnect.addEventListener('click', toggleConnect);
elements.btnEstop.addEventListener('click', emergencyStop);
elements.btnVideoToggle.addEventListener('click', toggleVideo);

elements.btnLight.addEventListener('click', () => {
    state.lightEnabled = !state.lightEnabled;
    elements.btnLight.classList.toggle('active', state.lightEnabled);
    log(`照明已${state.lightEnabled ? '开启' : '关闭'}`);
    // Send updated light state immediately
    sendControlCommand(state.move.speed, state.move.turn);
});

// Initial Log
log("系统就绪，等待连接...");
