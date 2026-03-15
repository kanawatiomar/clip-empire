const { contextBridge, ipcRenderer } = require('electron');

// Expose limited API to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  refreshData: () => ipcRenderer.send('refresh-data'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  onDataRefreshed: (callback) => ipcRenderer.on('data-refreshed', callback),
});

console.log('Preload script loaded with contextIsolation enabled');
