const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Set env vars
process.env.ELECTRON_MIRROR = 'https://npmmirror.com/mirrors/electron/';
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

// Override cache path to local project to avoid permission issues
const localCache = path.join(__dirname, '.electron-cache');
if (!fs.existsSync(localCache)) fs.mkdirSync(localCache);

console.log('Running electron install script with custom env...');
console.log('Cache path:', localCache);

// Mock user home/appdata to local folder to bypass permission issues if possible
// Note: electron-download might use 'env-paths' which looks at LOCALAPPDATA
// We try to set ELECTRON_CACHE directly which some versions support
process.env.ELECTRON_CACHE = localCache;
process.env.electron_config_cache = localCache; 

try {
  const installScriptPath = path.join(__dirname, 'node_modules', 'electron', 'install.js');
  if (fs.existsSync(installScriptPath)) {
    execSync(`node "${installScriptPath}"`, { stdio: 'inherit' });
    console.log('Install script completed.');
  } else {
    console.error('install.js not found!');
  }
} catch (error) {
  console.error('Install failed:', error.message);
}
