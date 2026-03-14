const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

// Set userData path to project directory to avoid sandbox restrictions
app.setPath('userData', path.join(__dirname, 'userData'));

const net = require('net');
const dgram = require('dgram');
const zlib = require('zlib');

let mainWindow;
let client;
let udpServer;
let isConnected = false;
const HOST = '127.0.0.1';
const PORT = 8888;
const UDP_PORT = 8889;

const HEADER = Buffer.from([0xAA, 0x55]);

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

  mainWindow.loadFile('index.html');
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
    console.log(`UDP server error:\n${err.stack}`);
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
    console.log(`UDP server listening ${address.address}:${address.port}`);
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
    console.log('Connected to Simulator');
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
        console.error('Parse error', e);
      }

      buffer = buffer.slice(totalLen);
    }
  });

  client.on('close', () => {
    console.log('Connection closed');
    isConnected = false;
    mainWindow.webContents.send('connection-status', 'Disconnected');
  });

  client.on('error', (err) => {
    console.error('Connection error: ' + err.message);
    mainWindow.webContents.send('connection-status', 'Error: ' + err.message);
  });
}

function sendPacket(cmdId, payload) {
  if (!client) {
    console.log('sendPacket error: Client not initialized');
    return;
  }
  if (client.destroyed) {
    console.log('sendPacket error: Client destroyed/disconnected');
    return;
  }

  console.log(`Sending Packet: Cmd=${cmdId}, Payload=${JSON.stringify(payload)}`);

  const payloadBuf = Buffer.from(JSON.stringify(payload));
  const length = payloadBuf.length;
  
  const dataToCheck = Buffer.concat([Buffer.from([cmdId]), payloadBuf]);
  // Use crc32 from zlib (async version is more standard in node, but sync exists in recent versions)
  // Actually, node's zlib.crc32 is available since v14.17.0, but sometimes it's better to use crc32 package or simple implementation if missing
  // Let's check if zlib.crc32Sync exists, if not use a polyfill or crc32 library
  // Electron 28 uses Node 18+, so zlib.crc32 should be there.
  // Wait, zlib.crc32Sync is NOT a standard node function name. It's zlib.crc32(buffer, [prev]).
  // BUT zlib.crc32 returns the value directly.
  
  const crc = zlib.crc32(dataToCheck); 

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
      console.log('Could not send stop video command:', e.message);
    }
    
    // Allow a small delay for the packet to be sent
    setTimeout(() => {
      if (client) {
        client.destroy();
        client = null;
        console.log('Disconnected manually');
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
  console.log(`IPC: video-control invoked with enabled=${enabled}`);
  sendPacket(0x10, { enabled });
});

ipcMain.handle('toggle-real-photo', () => {
  console.log('IPC: toggle-real-photo');
  sendPacket(0x11, {});
});

ipcMain.handle('snapshot', () => {
  console.log('IPC: snapshot');
  sendPacket(0x12, {});
});

ipcMain.handle('toggle-recording', () => {
  console.log('IPC: toggle-recording');
  sendPacket(0x13, {});
});
