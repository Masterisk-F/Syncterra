import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    // バックエンドのポート番号を取得
    getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
});
