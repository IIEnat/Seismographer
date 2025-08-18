// Responsible for exposing the Electron API to the renderer process

import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

type Listener = (...args: any[]) => void

function expose() {
  // toolkit (unchanged)
  contextBridge.exposeInMainWorld('electron', electronAPI)

  // custom API for your renderer
  contextBridge.exposeInMainWorld('api', {
    // invoke-style calls
    invoke: (channel: string, ...args: any[]) => ipcRenderer.invoke(channel, ...args),

    // event subscription; returns an unsubscribe fn
    on: (channel: string, listener: Listener) => {
      const wrapped = (_evt: Electron.IpcRendererEvent, ...args: any[]) => listener(...args)
      ipcRenderer.on(channel, wrapped)
      return () => ipcRenderer.removeListener(channel, wrapped)
    },

    // optional manual remove if you kept the same fn reference
    off: (channel: string, listener: Listener) => {
      ipcRenderer.removeListener(channel, listener as any)
    },

    // your existing helper
    getData: () => ipcRenderer.invoke('get-data'),
  })
}

if (process.contextIsolated) {
  try { expose() } catch (e) { console.error(e) }
} else {
  // fallback without isolation
  // @ts-ignore
  window.electron = electronAPI
  // @ts-ignore
  window.api = {
    invoke: (ch: string, ...a: any[]) => ipcRenderer.invoke(ch, ...a),
    on: (ch: string, cb: Listener) => {
      const wrapped = (_e: any, ...args: any[]) => cb(...args)
      ipcRenderer.on(ch, wrapped)
      return () => ipcRenderer.removeListener(ch, wrapped)
    },
    off: (ch: string, cb: Listener) => ipcRenderer.removeListener(ch, cb as any),
    getData: () => ipcRenderer.invoke('get-data'),
  }
}
