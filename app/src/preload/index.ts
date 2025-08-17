import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

if (process.contextIsolated) {
  try {
    // Expose toolkit APIs
    contextBridge.exposeInMainWorld('electron', electronAPI)

    // Expose custom API
    contextBridge.exposeInMainWorld('api', {
      getData: () => ipcRenderer.invoke('get-data')
    })
  } catch (error) {
    console.error(error)
  }
} else {
  // fallback if contextIsolation is disabled
  // @ts-ignore
  window.electron = electronAPI
  // @ts-ignore
  window.api = {
    getData: () => ipcRenderer.invoke('get-data')
  }
}
