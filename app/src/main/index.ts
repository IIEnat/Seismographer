import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { spawn } from 'child_process'
import path from 'path'

/* ------------ Python helpers ------------ */
function pyCmdAndArgs(scriptAbs: string): { cmd: string; args: string[] } {
  if (process.platform === 'win32') {
    // Use Windows launcher if present; falls back to python in PATH
    return require('fs').existsSync('C:\\Windows\\py.exe')
      ? { cmd: 'py', args: ['-3', scriptAbs] }
      : { cmd: 'python', args: [scriptAbs] }
  }
  return { cmd: 'python3', args: [scriptAbs] }
}

function pyScriptPath(): string {
  if (!app.isPackaged) {
    // Dev: point to project source (Windows path, not /mnt/…)
    return path.resolve(app.getAppPath(), 'src', 'main', 'backend.py')
  }
  // Prod: place via electron-builder extraResources -> backend/backend.py
  return path.join(process.resourcesPath, 'backend', 'backend.py')
}

/* ------------ Window ------------ */
function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true
    }
  })

  mainWindow.maximize()

  // Allow OpenStreetMap tiles
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; img-src 'self' https://*.tile.openstreetmap.org data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
        ]
      }
    })
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

/* ------------ App lifecycle + IPC ------------ */
app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.electron')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Run Python and return stdout as string
  ipcMain.handle('get-data', async () => new Promise((resolve, reject) => {
    const script = pyScriptPath()
    const { cmd, args } = pyCmdAndArgs(script)

    console.log('[PY] spawn:', cmd, args.join(' '), 'cwd=', app.getAppPath())

    const py = spawn(cmd, args, {
      cwd: app.getAppPath(),
      shell: process.platform === 'win32',
      windowsHide: true
    })

    let out = ''
    let err = ''

    py.stdout.on('data', d => { out += d.toString() })
    py.stderr.on('data', d => { err += d.toString() })
    py.on('error', e => {
      console.error('[PY] spawn error:', e)
      reject(new Error('Failed to start Python: ' + e.message))
    })
    py.on('close', code => {
      if (err) console.error('[PY] stderr:\n' + err)
      console.log('[PY] exit code:', code)
      console.log('[PY] stdout:', out.trim())
      if (code === 0) resolve(out.trim())
      else reject(new Error('Python exited with code ' + code))
    })
  }))

  ipcMain.on('ping', () => console.log('pong'))

  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
