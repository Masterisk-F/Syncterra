export interface ElectronAPI {
    getBackendPort: () => Promise<number>;
}

declare global {
    interface Window {
        electronAPI?: ElectronAPI;
    }
}
