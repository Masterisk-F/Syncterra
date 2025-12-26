import React, { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { notifications } from '@mantine/notifications';
import { syncFiles } from '../../api';
import { useWebSocket } from '../../api/useWebSocket';

interface SyncContextType {
    isSyncing: boolean;
    progress: number;
    logs: string[];
    isLogDrawerOpen: boolean;
    setIsLogDrawerOpen: (open: boolean) => void;
    handleSync: (trackCount?: number) => Promise<void>;
    addLog: (message: string) => void;
    isConnected: boolean;
}

const SyncContext = createContext<SyncContextType | undefined>(undefined);

export const SyncProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [isSyncing, setIsSyncing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState<string[]>([]);
    const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);

    const addLog = useCallback((message: string) => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [...prev, `[${timestamp}] ${message}`]);
    }, []);

    const handleWebSocketMessage = useCallback((message: string) => {
        addLog(message);
    }, [addLog]);

    const handleWebSocketProgress = useCallback((progressValue: number) => {
        setProgress(progressValue);
    }, []);

    const { isConnected } = useWebSocket(
        handleWebSocketMessage,
        handleWebSocketProgress
    );

    const handleSync = useCallback(async (trackCount?: number) => {
        setIsSyncing(true);
        setIsLogDrawerOpen(true);
        setProgress(0);
        setLogs([]);
        addLog('同期を開始しました...');

        if (trackCount !== undefined) {
            addLog(`同期対象: ${trackCount} ファイル`);
        }

        try {
            await syncFiles();
            addLog('同期完了');
            notifications.show({ title: '同期完了', message: 'ファイルの同期が完了しました', color: 'green' });
        } catch (error) {
            console.error('Sync failed:', error);
            addLog('同期失敗: ' + error);
            notifications.show({ title: 'エラー', message: '同期に失敗しました', color: 'red' });
        } finally {
            setIsSyncing(false);
            setProgress(100);
        }
    }, [addLog]);

    return (
        <SyncContext.Provider
            value={{
                isSyncing,
                progress,
                logs,
                isLogDrawerOpen,
                setIsLogDrawerOpen,
                handleSync,
                addLog,
                isConnected,
            }}
        >
            {children}
        </SyncContext.Provider>
    );
};

export const useSync = () => {
    const context = useContext(SyncContext);
    if (context === undefined) {
        throw new Error('useSync must be used within a SyncProvider');
    }
    return context;
};
