const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  connect: () => ipcRenderer.invoke('connect'),
  disconnect: () => ipcRenderer.invoke('disconnect'),
  sendControl: (data) => ipcRenderer.invoke('control', data),
  setVideo: (enabled) => ipcRenderer.invoke('video-control', enabled),
  onTelemetry: (callback) => ipcRenderer.on('telemetry-data', (event, value) => callback(value)),
  onStatus: (callback) => ipcRenderer.on('connection-status', (event, value) => callback(value)),
  onVideoFrame: (callback) => ipcRenderer.on('video-frame', (event, base64Img) => callback(base64Img))
});
