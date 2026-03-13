let isVideoEnabled = false;
let connectionStatus = 'Disconnected';

function updateOverlay() {
    const overlay = document.getElementById('video-overlay');
    const iconContainer = document.getElementById('overlay-icon');
    const textContainer = document.getElementById('overlay-text');
    
    if (!overlay || !iconContainer || !textContainer) return;

    // State 3: Video On (Hidden)
    if (connectionStatus === 'Connected' && isVideoEnabled) {
        overlay.classList.add('hidden');
        return;
    }

    // Show overlay
    overlay.classList.remove('hidden');
    
    // State 1: Disconnected
    if (connectionStatus !== 'Connected') {
        // Plug Icon
        iconContainer.innerHTML = '<svg viewBox="0 0 24 24"><path d="M16,7V3H8V7H6V11C6,13.36 7.64,15.33 9.87,15.85L9,21H15L14.13,15.85C16.36,15.33 18,13.36 18,11V7H16M14,11A2,2 0 0,1 12,13A2,2 0 0,1 10,11V7H14V11Z" /></svg>';
        textContainer.innerText = "请连接远程管道机器人";
    }
    // State 2: Connected, Video Off
    else if (connectionStatus === 'Connected' && !isVideoEnabled) {
        // Video Icon
        iconContainer.innerHTML = '<svg viewBox="0 0 24 24"><path d="M17,10.5V7A1,1 0 0,0 16,6H4A1,1 0 0,0 3,7V17A1,1 0 0,0 4,18H16A1,1 0 0,0 17,17V13.5L21,17.5V6.5L17,10.5Z" /></svg>';
        textContainer.innerText = "请开启视频";
    }
}

function log(msg) {
    const el = document.getElementById('log');
    if (el) {
        el.innerHTML += `<div>[${new Date().toLocaleTimeString()}] ${msg}</div>`;
        el.scrollTop = el.scrollHeight;
    }
}

// Status Handler
window.api.onStatus((status) => {
    const el = document.getElementById('status');
    const btn = document.getElementById('btn-connect');
    
    const statusMap = {
        'Connected': '已连接',
        'Disconnected': '未连接',
    };
    const displayStatus = statusMap[status] || status;
    
    connectionStatus = status; // Update global status
    updateOverlay(); // Update overlay based on new status

    el.innerText = displayStatus;
    el.style.color = status === 'Connected' ? '#4CAF50' : '#ff5555';
    
    // Update button state
    if (status === 'Connected') {
        btn.innerText = "断开连接";
        btn.className = "btn btn-danger";
        btn.onclick = disconnect;
    } else {
        btn.innerText = "连接管道机器人";
        btn.className = "btn";
        btn.onclick = connect;
        // Ensure video is cleared if disconnected from server side
        if (isVideoEnabled) {
             isVideoEnabled = false;
             document.getElementById('btn-video').innerText = "开启视频";
             document.getElementById('btn-video').className = "btn";
             document.getElementById('video-feed').src = "";
             updateOverlay();
        }
    }
    
    log(`状态: ${displayStatus}`);
});

// Telemetry Handler
window.api.onTelemetry((data) => {
    document.getElementById('battery').innerText = data.battery.toFixed(1);
    document.getElementById('pressure').innerText = data.pressure.toFixed(1);
    document.getElementById('temp').innerText = data.temperature.toFixed(1);
    document.getElementById('pitch').innerText = data.pitch.toFixed(1);
});

// Video Handling
const imgEl = document.getElementById('video-feed');

window.api.onVideoFrame((base64Img) => {
    const src = `data:image/jpeg;base64,${base64Img}`;
    imgEl.src = src;
});

function connect() {
    log("正在连接...");
    window.api.connect();
}

function disconnect() {
    log("正在断开...");
    window.api.disconnect();
    // Reset video state in UI
    isVideoEnabled = false;
    connectionStatus = 'Disconnected'; // Force update for immediate UI feedback
    updateOverlay();

    const btn = document.getElementById('btn-video');
    btn.innerText = "开启视频";
    btn.className = "btn";
    imgEl.src = ""; 
}

function updateControl() {
    const speed = parseFloat(document.getElementById('speed').value);
    const turn = parseFloat(document.getElementById('turn').value);
    
    document.getElementById('speed-val').innerText = speed.toFixed(1);
    document.getElementById('turn-val').innerText = turn.toFixed(1);

    window.api.sendControl({ speed, turn });
}

function toggleVideo() {
    isVideoEnabled = !isVideoEnabled;
    log(`切换视频状态: ${isVideoEnabled}`);
    window.api.setVideo(isVideoEnabled)
        .then(() => log("视频指令已发送"))
        .catch(err => log(`视频指令错误: ${err}`));
    
    const btn = document.getElementById('btn-video');
    btn.innerText = isVideoEnabled ? "停止视频" : "开启视频";
    btn.className = isVideoEnabled ? "btn btn-danger" : "btn";
    if (!isVideoEnabled) {
        imgEl.src = ""; // Clear
    }
    updateOverlay();
}

function takeScreenshot() {
    if (!imgEl.src || imgEl.src.length < 100) {
        alert("无视频信号!");
        return;
    }
    const a = document.createElement('a');
    a.href = imgEl.src;
    a.download = `截图_${new Date().toISOString().replace(/:/g,'-')}.jpg`;
    a.click();
    log("截图已保存");
}

