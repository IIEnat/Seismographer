// Launches everything here and handles the main process logic
// This is the main entry point for the Electron app

import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import fs from 'fs'
import { startReceiverBridge, stopReceiverBridge } from './receiver-bridge'

/* ------------ Python helpers ------------ */
function pyCmdAndArgs(scriptAbs: string, extraArgs: string[] = []): { cmd: string; args: string[] } {
  if (process.platform === 'win32') {
    return fs.existsSync('C:\\Windows\\py.exe')
      ? { cmd: 'py', args: ['-3', scriptAbs, ...extraArgs] }
      : { cmd: 'python', args: [scriptAbs, ...extraArgs] }
  }
  return { cmd: 'python3', args: [scriptAbs, ...extraArgs] }
}

function receiverScriptPath(): string {
  // Keep Python out of src/. Use resources/python for both dev & prod.
  if (!app.isPackaged) {
    return path.resolve(app.getAppPath(), 'resources', 'python', 'seedlink_multi_receiver.py')
  }
  return path.join(process.resourcesPath, 'python', 'seedlink_multi_receiver.py')
}

/* ------------ Start/stop persistent receiver ------------ */
let rxProc: ChildProcess | null = null

function startReceiver(): void {
  const script = receiverScriptPath()
  const args = [
    '--http-port', process.env.HTTP_PORT ?? '8081',
    '--reclen', '4096',
    '--metric', 'rms',
    '--source', '127.0.0.1:18001@XX.JINJ1..BHZ@-31.3447,115.8923',
    '--source', '127.0.0.1:18002@XX.JINJ2..BHZ@-31.3752,115.9231',
    '--source', '127.0.0.1:18003@XX.JINJ3..BHZ@-31.3433,115.9667'
  ]

  const { cmd, args: fullArgs } = pyCmdAndArgs(script, args)
  const cwd = path.dirname(script)

  console.log('[RX] spawn:', cmd, fullArgs.join(' '), 'cwd=', cwd)
  rxProc = spawn(cmd, fullArgs, {
    cwd,
    shell: process.platform === 'win32',
    windowsHide: true
  })

  rxProc.stdout?.on('data', d => console.log('[RX]', d.toString().trim()))
  rxProc.stderr?.on('data', d => console.error('[RX!]', d.toString().trim()))
  rxProc.on('exit', code => {
    console.log('[RX] exited with code', code)
    rxProc = null
  })
}

function stopReceiver(): void {
  if (!rxProc) return
  try { rxProc.kill() } catch { /* ignore */ }
  rxProc = null
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

  // Start Python receiver once at app start
  startReceiver()

  // One-off Python script runner (kept from your code)
  ipcMain.handle('get-data', async () => new Promise((resolve, reject) => {
    // If you still have a separate backend.py, keep your existing logic here.
    const script = (!app.isPackaged)
      ? path.resolve(app.getAppPath(), 'src', 'main', 'backend.py')
      : path.join(process.resourcesPath, 'backend', 'backend.py')

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

  const win = BrowserWindow.getAllWindows()[0]  // or the instance you just created
  startReceiverBridge(win)  
})

app.on('before-quit', () => {
  stopReceiverBridge()
})
app.on('window-all-closed', () => {
  stopReceiverBridge()
})
