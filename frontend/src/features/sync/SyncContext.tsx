import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { notifications } from '@mantine/notifications';
import { syncFiles, scanFiles } from '../../api';
import { useWebSocket } from '../../api/useWebSocket';

interface SyncContextType {
  isSyncing: boolean;
  isScanning: boolean;
  progress: number;
  logs: string[];
  isLogDrawerOpen: boolean;
  setIsLogDrawerOpen: (open: boolean) => void;
  handleSync: (trackCount?: number) => Promise<void>;
  handleScan: () => Promise<void>;
  addLog: (message: string) => void;
  isConnected: boolean;
  lastUpdateId: number;
  processName: string;
}

const SyncContext = createContext<SyncContextType | undefined>(undefined);

export const SyncProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [isSyncing, setIsSyncing] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [lastUpdateId, setLastUpdateId] = useState(0);
  const [processName, setProcessName] = useState('');

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, `[${timestamp}] ${message}`]);
  }, []);

  const handleWebSocketMessage = useCallback(
    (message: string) => {
      addLog(message);

      // スキャン完了を検出
      if (message.includes('Scan complete')) {
        setLastUpdateId(Date.now());
        setIsScanning(false);
        notifications.show({
          title: 'スキャン完了',
          message: 'ファイルの読み込みが完了しました',
          color: 'green',
        });
      }

      // 同期完了を検出
      if (message.includes('Sync complete')) {
        setLastUpdateId(Date.now());
        setIsSyncing(false);
        setProgress(100);
        notifications.show({
          title: '同期完了',
          message: 'ファイルの同期が完了しました',
          color: 'green',
        });
      }
    },
    [addLog]
  );

  const handleWebSocketProgress = useCallback((progressValue: number) => {
    setProgress(progressValue);
  }, []);

  const { isConnected } = useWebSocket(
    handleWebSocketMessage,
    handleWebSocketProgress
  );

  const handleSync = useCallback(
    async (trackCount?: number) => {
      if (isSyncing || isScanning) {
        console.warn(
          'Sync or Scan is already in progress. Ignoring handleSync call.'
        );
        return;
      }

      setProcessName('同期');
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
        addLog('同期処理を受け付けました（バックグラウンドで開始）');
      } catch (error) {
        console.error('Sync failed:', error);
        addLog('同期開始失敗: ' + error);
        notifications.show({
          title: 'エラー',
          message: '同期の開始に失敗しました',
          color: 'red',
        });
        setIsSyncing(false);
      }
    },
    [isSyncing, isScanning, addLog]
  );

  const handleScan = useCallback(async () => {
    if (isSyncing || isScanning) {
      console.warn(
        'Sync or Scan is already in progress. Ignoring handleScan call.'
      );
      return;
    }

    setProcessName('スキャン');
    setIsScanning(true);
    setIsLogDrawerOpen(true);
    setProgress(0);
    setLogs([]);
    addLog('スキャンを開始しました...');

    try {
      await scanFiles();
      // 完了はWebSocketメッセージ ("Scan complete") で検知してリロードフラグを立てる
    } catch (error) {
      console.error('Scan failed:', error);
      addLog('スキャン失敗: ' + error);
      notifications.show({
        title: 'エラー',
        message: 'スキャンに失敗しました',
        color: 'red',
      });
      setIsScanning(false);
    }
  }, [isSyncing, isScanning, addLog]);

  return (
    <SyncContext.Provider
      value={{
        isSyncing,
        isScanning,
        progress,
        logs,
        isLogDrawerOpen,
        setIsLogDrawerOpen,
        handleSync,
        handleScan,
        addLog,
        isConnected,
        lastUpdateId,
        processName,
      }}
    >
      {children}
    </SyncContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useSync = () => {
  const context = useContext(SyncContext);
  if (context === undefined) {
    throw new Error('useSync must be used within a SyncProvider');
  }
  return context;
};
