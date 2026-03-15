const { app, BrowserWindow, Menu, Tray, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

let mainWindow;
let tray;
let pythonProcess;
let isQuitting = false;

// Paths
const DASHBOARD_DIR = path.join(__dirname, '..', 'dashboard');
const PYTHON_PATH = 'C:\\Users\\kanaw\\AppData\\Local\\Programs\\Python\\Python311\\python.exe';
const CONTROL_API = path.join(DASHBOARD_DIR, 'control_api.py');
const GENERATE_DATA = path.join(DASHBOARD_DIR, 'generate_data.py');
const API_URL = 'http://127.0.0.1:8787/';
const LOADING_HTML = path.join(__dirname, 'loading.html');

/**
 * Check if the server is ready by polling the API
 */
function waitForServer(maxAttempts = 30, delayMs = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const checkServer = () => {
      http.get(API_URL, (res) => {
        if (res.statusCode === 200) {
          console.log('✓ Server is ready');
          resolve(true);
        } else {
          attempt();
        }
      }).on('error', attempt);

      function attempt() {
        attempts++;
        if (attempts >= maxAttempts) {
          reject(new Error('Server did not start in time'));
        } else {
          setTimeout(checkServer, delayMs);
        }
      }
    };

    checkServer();
  });
}

/**
 * Spawn the Python control API server
 */
function startPythonServer() {
  return new Promise((resolve, reject) => {
    console.log(`Spawning Python server: ${PYTHON_PATH} ${CONTROL_API}`);

    pythonProcess = spawn(PYTHON_PATH, [CONTROL_API], {
      cwd: DASHBOARD_DIR,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let serverOutput = '';
    pythonProcess.stdout.on('data', (data) => {
      serverOutput += data.toString();
      console.log(`[Python] ${data.toString().trim()}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Error] ${data.toString().trim()}`);
    });

    pythonProcess.on('error', (err) => {
      console.error('Failed to start Python process:', err);
      reject(err);
    });

    pythonProcess.on('close', (code) => {
      if (code !== 0 && !isQuitting) {
        console.error(`Python process exited with code ${code}`);
      }
    });

    // Give the process a moment to start before checking
    setTimeout(() => {
      waitForServer()
        .then(() => resolve(pythonProcess))
        .catch(reject);
    }, 500);
  });
}

/**
 * Create the main application window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false,
      nodeIntegration: false,
    },
    show: false, // Don't show until ready
    icon: path.join(DASHBOARD_DIR, 'icon.svg'),
    backgroundColor: '#0a0e17',
  });

  // Load loading screen first
  mainWindow.loadFile(LOADING_HTML);
  mainWindow.show();

  // Wait for server then load dashboard
  waitForServer()
    .then(() => {
      console.log('Loading dashboard from', API_URL);
      mainWindow.loadURL(API_URL);
    })
    .catch((err) => {
      console.error('Failed to start server:', err);
      mainWindow.webContents.executeJavaScript(`
        document.body.innerHTML = '<div style="color: #c9a84c; text-align: center; margin-top: 50px;">Error starting server: ${err.message}</div>';
      `);
    });

  // Open DevTools in development (comment out for production)
  // mainWindow.webContents.openDevTools();

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

/**
 * Create system tray menu
 */
function createTray() {
  const { nativeImage } = require('electron');
  
  // Try to load icon, but fall back to a simple generated one
  let trayIcon = createSimpleTrayIcon();

  tray = new Tray(trayIcon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open Dashboard',
      click: () => {
        mainWindow.show();
        mainWindow.focus();
      },
    },
    {
      label: 'Refresh Data',
      click: () => {
        refreshData();
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip('Clip Empire Dashboard');
}

/**
 * Create a simple tray icon (16x16 colored square)
 * Uses nativeImage to create a basic icon from scratch
 */
function createSimpleTrayIcon() {
  const { nativeImage } = require('electron');
  
  // For Windows tray, we can try using a Data URL or just use a simple approach
  // Create a 1x1 gold pixel and scale it (simplest approach)
  try {
    // Use a simple PNG data URL with a gold square
    const goldColor = nativeImage.createFromDataURL(
      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEBQIAX8jx0gAAAABJRU5ErkJggg=='
    );
    return goldColor;
  } catch (err) {
    // Fallback: just use empty icon, Windows will use default
    console.warn('Tray icon creation skipped, using system default');
    return nativeImage.createEmpty();
  }
}

/**
 * Refresh dashboard data by running generate_data.py
 */
function refreshData() {
  console.log('Running data refresh...');
  const refreshProcess = spawn(PYTHON_PATH, [GENERATE_DATA], {
    cwd: DASHBOARD_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  refreshProcess.on('close', (code) => {
    if (code === 0) {
      console.log('Data refresh completed');
      // Reload the dashboard
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.reload();
      }
    } else {
      console.error(`Data refresh failed with code ${code}`);
    }
  });
}

/**
 * App lifecycle
 */
app.on('ready', async () => {
  try {
    // Start Python server
    await startPythonServer();
    console.log('Python server started');

    // Create window and tray
    createWindow();
    createTray();
  } catch (err) {
    console.error('Failed to initialize app:', err);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  // On macOS, applications stay active until user quits explicitly
  if (process.platform !== 'darwin') {
    isQuitting = true;
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null || mainWindow.isDestroyed()) {
    createWindow();
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  if (pythonProcess) {
    console.log('Killing Python process...');
    pythonProcess.kill();
  }
});

/**
 * IPC handlers for dashboard -> main process communication
 */
ipcMain.on('refresh-data', () => {
  refreshData();
});

ipcMain.on('window-minimize', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.on('window-close', () => {
  if (mainWindow) {
    mainWindow.hide();
  }
});

module.exports = { app };
