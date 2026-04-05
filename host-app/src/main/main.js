const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const config = require('../config/settings.js');

// Set userData path to project directory to avoid sandbox restrictions
app.setPath('userData', path.join(__dirname, '..', '..', 'userData'));

const net = require('net');
const dgram = require('dgram');

let mainWindow;
let client;
let udpServer;
let isConnected = false;
const HOST = config.HOST;
const PORT = config.TCP_PORT;
const UDP_PORT = config.UDP_PORT;

const HEADER = config.HEADER;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  createWindow();
  startUdpServer();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// UDP Video Receiver
function startUdpServer() {
  udpServer = dgram.createSocket('udp4');
  
  udpServer.on('error', (err) => {
    udpServer.close();
  });

  udpServer.on('message', (msg, rinfo) => {
    // Process video frames regardless of TCP connection state (Independent Video Link)
    // msg is the JPEG buffer
    if (mainWindow && !mainWindow.isDestroyed()) {
      // Convert to base64 for easy display in renderer
      const base64Img = msg.toString('base64');
      mainWindow.webContents.send('video-frame', base64Img);
    }
  });

  udpServer.on('listening', () => {
    const address = udpServer.address();
  });

  udpServer.bind(UDP_PORT);
}

// TCP Communication Logic
let buffer = Buffer.alloc(0);

function connect() {
  if (client) {
    client.destroy();
  }
  
  client = new net.Socket();

  client.connect(PORT, HOST, () => {
    isConnected = true;
    mainWindow.webContents.send('connection-status', 'Connected');
  });

  client.on('data', (data) => {
    buffer = Buffer.concat([buffer, data]);
    
    while (true) {
      if (buffer.length < 11) break; 

      if (buffer[0] !== 0xAA || buffer[1] !== 0x55) {
        const idx = buffer.indexOf(HEADER, 1);
        if (idx !== -1) {
          buffer = buffer.slice(idx);
          continue;
        } else {
          buffer = Buffer.alloc(0);
          break;
        }
      }

      const length = buffer.readUInt32BE(2);
      const totalLen = 2 + 4 + 1 + length + 4;

      if (buffer.length < totalLen) break;

      const cmdId = buffer.readUInt8(6);
      const payloadBuf = buffer.slice(7, 7 + length);
      
      try {
        const payload = JSON.parse(payloadBuf.toString());
        if (cmdId === 0x80) {
          mainWindow.webContents.send('telemetry-data', payload);
        }
      } catch (e) {
      }

      buffer = buffer.slice(totalLen);
    }
  });

  client.on('close', () => {
    isConnected = false;
    mainWindow.webContents.send('connection-status', 'Disconnected');
  });

  client.on('error', (err) => {
    mainWindow.webContents.send('connection-status', 'Error: ' + err.message);
  });
}

function sendPacket(cmdId, payload) {
  if (!client) {
    return;
  }
  if (client.destroyed) {
    return;
  }

  const payloadBuf = Buffer.from(JSON.stringify(payload));
  const length = payloadBuf.length;
  
  const dataToCheck = Buffer.concat([Buffer.from([cmdId]), payloadBuf]);
  // zlib.crc32 was added in Node.js v14.17.0
  // However, in some Electron environments or older node versions it might be missing or behaves differently
  // Let's use a simple CRC32 implementation to be safe and dependency-free
  
  const crc = crc32(dataToCheck); 

  const packet = Buffer.concat([
    HEADER,
    Buffer.alloc(4), 
    Buffer.from([cmdId]),
    payloadBuf,
    Buffer.alloc(4) 
  ]);
  
  packet.writeUInt32BE(length, 2);
  packet.writeUInt32BE(crc, 7 + length);

  client.write(packet);
}

function disconnect() {
  if (client) {
    // Send stop video command before destroying connection
    try {
      sendPacket(0x10, { enabled: false });
    } catch (e) {
    }
    
    // Allow a small delay for the packet to be sent
    setTimeout(() => {
      if (client) {
        client.destroy();
        client = null;
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('connection-status', 'Disconnected');
        }
      }
    }, 50);
  }
}

ipcMain.handle('connect', () => {
  connect();
});

ipcMain.handle('disconnect', () => {
  disconnect();
});

ipcMain.handle('control', (event, data) => {
  sendPacket(0x02, data);
});

ipcMain.handle('video-control', (event, enabled) => {
  sendPacket(0x10, { enabled });
});

ipcMain.handle('toggle-real-photo', () => {
  sendPacket(0x11, {});
});

ipcMain.handle('snapshot', () => {
  sendPacket(0x12, {});
});

ipcMain.handle('toggle-recording', () => {
  sendPacket(0x13, {});
});

// Simple CRC32 implementation
function crc32(buffer) {
  let crc = -1;
  for (let i = 0; i < buffer.length; i++) {
    crc = (crc >>> 8) ^ crcTable[(crc ^ buffer[i]) & 0xFF];
  }
  return (crc ^ -1) >>> 0;
}

const crcTable = new Uint32Array(256);
(function() {
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) {
      c = ((c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
    }
    crcTable[i] = c;
  }
})();
