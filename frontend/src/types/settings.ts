export type SyncMethod = 'adb' | 'ftp' | 'rsync';

export interface AppSettings {
    scanPaths: string[];
    excludeDirs: string[];
    targetExtensions: string[];
    syncDestPath: string;
    syncMethod: SyncMethod;

    // FTP settings
    ftpHost?: string;
    ftpPort?: number;
    ftpUser?: string;
    ftpPassword?: string;

    // Rsync settings
    rsyncHost?: string;
    rsyncPort?: number;
    rsyncUser?: string;
    rsyncPassword?: string;
    rsyncUseKey?: boolean;

    // ADB settings
    adbDeviceId?: string;
}

export const DEFAULT_SETTINGS: AppSettings = {
    scanPaths: [],
    excludeDirs: [],
    targetExtensions: ['mp3', 'm4a', 'mp4'],
    syncDestPath: '',
    syncMethod: 'adb',
    ftpPort: 21,
    rsyncPort: 22,
    rsyncUseKey: false,
};
