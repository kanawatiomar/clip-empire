# Clip Empire Dashboard - Electron Desktop App

A desktop application wrapper for the Clip Empire Dashboard, built with Electron and Python.

## Features

- **Native Desktop App**: Runs the Clip Empire Dashboard as a standalone Windows application
- **System Tray**: Minimizes to system tray instead of closing
- **Integrated Python Backend**: Automatically spawns and manages the Python control API server
- **Data Refresh**: One-click data refresh from the tray menu
- **Loading Screen**: Beautiful loading screen while the server initializes

## Prerequisites

- **Node.js** (v16+) - [Download](https://nodejs.org/)
- **Python 3.11** - [Download](https://www.python.org/downloads/)
  - Must be installed at: `C:\Users\kanaw\AppData\Local\Programs\Python\Python311\python.exe`
  - If your Python path differs, update `main.js` line 17

## Installation

### 1. Install Node Dependencies

```bash
cd electron
npm install
```

This installs:
- `electron` - Desktop app framework
- `electron-builder` - Packaging and installer creation

### 2. Verify Python Setup

Ensure Python 3.11 is installed and accessible:

```cmd
C:\Users\kanaw\AppData\Local\Programs\Python\Python311\python.exe --version
```

## Usage

### Development (with automatic reload)

```bash
npm start
```

This:
1. Spawns the Python control API server (port 8787)
2. Waits for the server to be ready
3. Opens the desktop app window
4. Displays a loading screen until the server responds

### Build Windows Installer

```bash
npm run build
```

This creates:
- **NSIS Installer** (`dist/Clip Empire Dashboard 1.0.0.exe`)
- **Portable Executable** (`dist/Clip Empire Dashboard 1.0.0.exe`)

Installer features:
- Install to custom directory
- Start Menu shortcuts
- Desktop shortcuts
- Uninstall support

## Architecture

### File Structure

```
electron/
├── main.js              # Main Electron process (server spawning, window management)
├── preload.js           # Context-isolated IPC bridge to renderer
├── loading.html         # Loading screen while Python server starts
├── package.json         # Node dependencies & electron-builder config
└── README.md            # This file
```

### How It Works

1. **App Start**: Electron main process spawns `control_api.py` as a child process
2. **Server Wait**: Polls `http://127.0.0.1:8787/` until the server responds
3. **Loading Screen**: Shows animated loading screen during startup
4. **Dashboard Load**: Once server is ready, loads the dashboard in the BrowserWindow
5. **System Tray**: Window minimizes to tray instead of closing
6. **Cleanup**: When app quits, the Python server process is killed gracefully

### Key Processes

- **control_api.py**: Serves the dashboard UI and handles API requests (port 8787)
- **generate_data.py**: Refreshes the dashboard data when triggered from the tray menu

## Troubleshooting

### App Won't Start

1. **Check Python path**: Verify Python 3.11 is at the expected path
   ```cmd
   dir "C:\Users\kanaw\AppData\Local\Programs\Python\Python311\"
   ```
2. **Update path in main.js**: If Python is elsewhere, edit line 17:
   ```javascript
   const PYTHON_PATH = 'C:\\your\\python\\path\\python.exe';
   ```
3. **Check logs**: Look for error messages in the loading screen or console

### Server Not Responding

1. Check that port 8787 is available:
   ```cmd
   netstat -ano | findstr :8787
   ```
2. Manually test the control API:
   ```cmd
   cd ../dashboard
   python control_api.py
   ```
3. Check Python dependencies in `dashboard/`:
   ```cmd
   pip install -r ../requirements.txt
   ```

### Build Fails

1. Ensure all dependencies are installed:
   ```bash
   npm install
   ```
2. Clear node_modules and try again:
   ```bash
   rmdir node_modules /s /q
   npm install
   npm run build
   ```

## Development

### Debugging

- **View main process logs**: Check the terminal where you ran `npm start`
- **View renderer logs**: Open DevTools in main.js (uncomment line 126)
- **Test without Python**: Replace `startPythonServer()` with a mock HTTP server

### IPC Communication

The preload script exposes these methods to the renderer:

```javascript
// In dashboard HTML/JS:
window.electronAPI.refreshData()      // Trigger data refresh
window.electronAPI.minimizeWindow()   // Minimize window
window.electronAPI.closeWindow()      // Hide window to tray
```

## Configuration

### Window Size

Edit `main.js` line 95-98 to change the default window dimensions:

```javascript
new BrowserWindow({
  width: 1400,    // Default width
  height: 900,    // Default height
  minWidth: 1024, // Minimum width
  minHeight: 700, // Minimum height
})
```

### Tray Menu

Edit `main.js` line 208-231 to customize tray menu items.

### Python Server Port

The app expects the Python server on port 8787. To change:

1. Update `CONTROL_API` URL in `main.js` line 24
2. Ensure `control_api.py` is configured to run on that port

## Distribution

### Installer Output

Built installers are saved to:
```
electron/dist/
├── Clip Empire Dashboard 1.0.0.exe  (NSIS Installer)
└── Clip Empire Dashboard 1.0.0.exe  (Portable)
```

Share these `.exe` files for distribution.

### Updating Version

Edit `package.json` line 3:

```json
"version": "1.0.1"
```

Then rebuild with `npm run build`.

## License

ISC

## Support

For issues, check:
- This README's Troubleshooting section
- The terminal output when running `npm start`
- The OpenClaw workspace logs at `C:\Users\kanaw\.openclaw\`
