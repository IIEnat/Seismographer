// Takes care of the receiver bridge between the main process and the renderer.
// Turning the HTTP data into IPC for the renderer

import { BrowserWindow, ipcMain } from 'electron'

let timer: NodeJS.Timeout | null = null

export function startReceiverBridge(win: BrowserWindow, base = 'http://127.0.0.1:8081') {
  // push /live to renderer every second
  stopReceiverBridge()
  timer = setInterval(async () => {
    try {
      const res = await fetch(`${base}/live`, { cache: 'no-store' })
      if (!res.ok) return
      const json = await res.json()
      win.webContents.send('receiver:live', json)
    } catch { /* ignore transient errors */ }
  }, 1000)

  // on-demand /wave?id=...
  ipcMain.handle('receiver:wave', async (_evt, id: string) => {
    const url = new URL(`${base}/wave`)
    url.searchParams.set('id', id)
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) throw new Error(`wave ${id} -> HTTP ${res.status}`)
    return res.json()
  })
}

export function stopReceiverBridge() {
  if (timer) { clearInterval(timer); timer = null }
  if ((ipcMain as any)._events?.['receiver:wave']) ipcMain.removeHandler('receiver:wave')
}
