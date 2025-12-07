import { useState, useMemo, useEffect, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule, themeQuartz, colorSchemeDarkBlue } from 'ag-grid-community';
import { Title, Paper, Stack, useMantineColorScheme, Button, Group, Loader, Text, Badge } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconRefresh, IconDeviceFloppy, IconPlayerPlay, IconTerminal2 } from '@tabler/icons-react';
import type { Track } from '../../types/track';
import ProcessLogDrawer from './ProcessLogDrawer';
import { getTracks, batchUpdateTracks, scanFiles, syncFiles } from '../../api';
import { useWebSocket } from '../../api/useWebSocket';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

// ファイルサイズをMB表示にフォーマット
const formatFileSize = (bytes: number): string => {
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

// 再生時間を分:秒表示にフォーマット
const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export default function AudioListPage() {
    const [rowData, setRowData] = useState<Track[]>([]);
    const [loading, setLoading] = useState(true);
    const { colorScheme } = useMantineColorScheme();

    // Control Panel State
    const [isScanning, setIsScanning] = useState(false);
    const [isSyncing, setIsSyncing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [logs, setLogs] = useState<string[]>([]);
    const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);

    const isProcessing = isScanning || isSyncing;

    const gridTheme = useMemo(() => {
        return colorScheme === 'dark'
            ? themeQuartz.withPart(colorSchemeDarkBlue)
            : themeQuartz;
    }, [colorScheme]);

    // WebSocket接続 - ログとプログレス受信
    const handleWebSocketMessage = useCallback((message: string) => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [`[${timestamp}] ${message}`, ...prev]);

        // スキャン完了を検出してトラック一覧を再読み込み
        if (message.includes('Scan complete')) {
            const reloadTracks = async () => {
                try {
                    const tracks = await getTracks();
                    const frontendTracks: Track[] = tracks.map(t => ({
                        id: t.id,
                        msg: '',
                        sync: t.sync,
                        title: t.title || '',
                        artist: t.artist || '',
                        album_artist: '',
                        composer: '',
                        album: t.album || '',
                        track_num: '',
                        length: 0,
                        file_name: t.file_name,
                        file_path: t.file_path,
                        file_path_to_relative: t.relative_path || '',
                        codec: '',
                        size: 0,
                        added_date: '',
                        update_date: '',
                    }));
                    setRowData(frontendTracks);
                    setIsScanning(false);
                } catch (error) {
                    console.error('Failed to reload tracks:', error);
                }
            };
            reloadTracks();
        }
    }, []);

    const handleWebSocketProgress = useCallback((progressValue: number) => {
        setProgress(progressValue);
    }, []);

    const { isConnected } = useWebSocket(
        handleWebSocketMessage,
        handleWebSocketProgress
    );

    // Load tracks from API
    useEffect(() => {
        const loadTracks = async () => {
            try {
                const tracks = await getTracks();
                // APIのTrack型をフロント型に変換（必要に応じて）
                const frontendTracks: Track[] = tracks.map(t => ({
                    id: t.id,
                    msg: '',
                    sync: t.sync,
                    title: t.title || '',
                    artist: t.artist || '',
                    album_artist: '',
                    composer: '',
                    album: t.album || '',
                    track_num: '',
                    length: 0,
                    file_name: t.file_name,
                    file_path: t.file_path,
                    file_path_to_relative: t.relative_path || '',
                    codec: '',
                    size: 0,
                    added_date: '',
                    update_date: '',
                }));
                setRowData(frontendTracks);
            } catch (error) {
                console.error('Failed to load tracks:', error);
                notifications.show({
                    title: 'エラー',
                    message: 'トラック一覧の読み込みに失敗しました',
                    color: 'red',
                });
            } finally {
                setLoading(false);
            }
        };
        loadTracks();
    }, []);

    // Add log helper
    const addLog = (message: string) => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [`[${timestamp}] ${message}`, ...prev]);
    };

    // Scan実行
    const handleScan = async () => {
        setIsScanning(true);
        setIsLogDrawerOpen(true);
        setProgress(0);
        setLogs([]);
        addLog('スキャンを開始しました...');

        try {
            await scanFiles();
            // トラック一覧の再読み込みはWebSocketの"Scan complete"メッセージで実行
        } catch (error) {
            console.error('Scan failed:', error);
            addLog('スキャン失敗: ' + error);
            notifications.show({ title: 'エラー', message: 'スキャンに失敗しました', color: 'red' });
            setIsScanning(false);
        }
    };

    // Sync実行
    const handleSync = async () => {
        setIsSyncing(true);
        setIsLogDrawerOpen(true);
        setProgress(0);
        setLogs([]);
        addLog('同期を開始しました...');

        const syncCount = rowData.filter(r => r.sync).length;
        addLog(`同期対象: ${syncCount} ファイル`);

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
    };

    // Save Sync Settings - syncフラグをバックエンドに保存
    const handleSaveSync = async () => {
        try {
            const changedTracks = rowData.filter(r => r.sync);
            if (changedTracks.length > 0) {
                await batchUpdateTracks(changedTracks.map(r => r.id), true);
            }
            const unchangedTracks = rowData.filter(r => !r.sync);
            if (unchangedTracks.length > 0) {
                await batchUpdateTracks(unchangedTracks.map(r => r.id), false);
            }
            notifications.show({
                title: '設定保存',
                message: '同期設定を保存しました',
                color: 'blue',
            });
        } catch (error) {
            console.error('Failed to save sync settings:', error);
            notifications.show({
                title: 'エラー',
                message: '設定の保存に失敗しました',
                color: 'red',
            });
        }
    };

    // Sync Toggle Handler
    const handleSyncToggle = (id: number, currentValue: boolean) => {
        setRowData(prev => prev.map(row =>
            row.id === id ? { ...row, sync: !currentValue } : row
        ));
    };

    // Since we need gridApi for selection, let's refactor slightly to store it
    const [gridApi, setGridApi] = useState<any>(null);

    const onGridReady = (params: any) => {
        setGridApi(params.api);
    };

    // Batch Paste Handler (Ctrl+V)
    const handleContainerPaste = async (_e: React.ClipboardEvent) => {
        if (!gridApi) return;

        const clipboardText = await navigator.clipboard.readText();
        const text = clipboardText.toLowerCase().trim();

        const isTrue = ['true', '1', '○', 'yes', 'on'].includes(text);
        const isFalse = ['false', '0', '', 'no', 'off'].includes(text);

        if (!isTrue && !isFalse) return;

        const newValue = isTrue;
        const selectedNodes = gridApi.getSelectedNodes();

        if (selectedNodes.length === 0) return;

        const updatedRows = rowData.map(row => {
            const isSelected = selectedNodes.some((node: any) => node.data.id === row.id);
            if (isSelected) {
                return { ...row, sync: newValue };
            }
            return row;
        });

        setRowData(updatedRows);
        notifications.show({
            title: '一括更新',
            message: `${selectedNodes.length}件の同期設定を${newValue ? 'ON' : 'OFF'}にしました`,
            color: 'teal'
        });
    };

    // カラム定義
    const columnDefs = useMemo<ColDef<Track>[]>(() => [
        {
            field: 'msg',
            headerName: '!',
            width: 50,
            cellStyle: { textAlign: 'center' },
        },
        {
            field: 'sync',
            headerName: '同期',
            width: 70,
            editable: false,
            cellRenderer: (params: any) => {
                return (
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            height: '100%',
                            width: '100%',
                            cursor: 'pointer'
                        }}
                        onClick={() => params.context.handleSyncToggle(params.data.id, params.value)}
                    >
                        <input
                            type="checkbox"
                            checked={params.value}
                            readOnly
                            style={{ cursor: 'pointer', margin: 0 }}
                        />
                    </div>
                );
            },
            cellStyle: { display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 0 } as any,
        },
        {
            field: 'title',
            headerName: 'タイトル',
            width: 200,
            filter: true,
            sortable: true,
        },
        {
            field: 'artist',
            headerName: 'アーティスト',
            width: 150,
            filter: true,
            sortable: true,
        },
        {
            field: 'album_artist',
            headerName: 'アルバムアーティスト',
            width: 150,
            filter: true,
            sortable: true,
        },
        {
            field: 'composer',
            headerName: '作曲者',
            width: 150,
            filter: true,
            sortable: true,
        },
        {
            field: 'album',
            headerName: 'アルバム',
            width: 200,
            filter: true,
            sortable: true,
        },
        {
            field: 'track_num',
            headerName: '#',
            width: 80,
            cellStyle: { textAlign: 'center' },
        },
        {
            field: 'length',
            headerName: '長さ',
            width: 90,
            valueFormatter: (params) => formatDuration(params.value),
            cellStyle: { textAlign: 'right' },
        },
        {
            field: 'file_name',
            headerName: 'ファイル名',
            width: 200,
            filter: true,
        },
        {
            field: 'file_path',
            headerName: 'ファイルパス',
            width: 300,
            filter: true,
        },
        {
            field: 'file_path_to_relative',
            headerName: '同期先相対パス',
            width: 250,
        },
        {
            field: 'codec',
            headerName: 'コーデック',
            width: 100,
            filter: true,
        },
        {
            field: 'size',
            headerName: 'サイズ',
            width: 110,
            valueFormatter: (params) => formatFileSize(params.value),
            cellStyle: { textAlign: 'right' },
        },
        {
            field: 'added_date',
            headerName: '追加日時',
            width: 170,
            sortable: true,
        },
        {
            field: 'update_date',
            headerName: '更新日時',
            width: 170,
            sortable: true,
        },
    ], []);

    const defaultColDef = useMemo<ColDef>(() => ({
        resizable: true,
        sortable: false,
        filter: false,
    }), []);

    if (loading) {
        return (
            <Stack align="center" justify="center" h={400}>
                <Loader size="lg" />
                <Text c="dimmed">トラック一覧を読み込み中...</Text>
            </Stack>
        );
    }

    return (
        <Stack gap="md" h="100%">
            <Paper p="md" withBorder radius="md">
                <Group justify="space-between" align="center">
                    <Group>
                        <Title order={2}>音楽ファイル一覧</Title>

                        <Badge
                            color={isConnected ? 'green' : 'gray'}
                            variant="dot"
                            size="sm"
                        >
                            {isConnected ? 'WebSocket接続中' : 'オフライン'}
                        </Badge>

                        <Button
                            leftSection={<IconRefresh size={20} />}
                            onClick={handleScan}
                            loading={isScanning}
                            disabled={isSyncing}
                            variant="default"
                            size="sm"
                        >
                            スキャン
                        </Button>

                        <Button
                            leftSection={<IconDeviceFloppy size={20} />}
                            onClick={handleSaveSync}
                            disabled={isProcessing}
                            color="blue"
                            variant="light"
                            size="sm"
                        >
                            設定保存
                        </Button>

                        <Button
                            leftSection={<IconPlayerPlay size={20} />}
                            onClick={handleSync}
                            loading={isSyncing}
                            disabled={isScanning}
                            color="green"
                            size="sm"
                        >
                            同期実行
                        </Button>
                    </Group>

                    <Button
                        leftSection={<IconTerminal2 size={20} />}
                        onClick={() => setIsLogDrawerOpen(true)}
                        variant="subtle"
                        size="sm"
                        color="gray"
                    >
                        ログ
                    </Button>
                </Group>
            </Paper>

            <ProcessLogDrawer
                opened={isLogDrawerOpen}
                onClose={() => setIsLogDrawerOpen(false)}
                isProcessing={isProcessing}
                processName={isScanning ? 'スキャン' : '同期'}
                progress={progress}
                logs={logs}
            />

            <Paper
                withBorder
                radius="md"
                style={{
                    height: 'calc(100vh - 180px)', // Adjusted height
                    display: 'flex',
                    flexDirection: 'column'
                }}
            >
                <div
                    style={{
                        height: '100%',
                        width: '100%'
                    }}
                    onPaste={handleContainerPaste}
                    tabIndex={0}
                >
                    <AgGridReact<Track>
                        onGridReady={onGridReady}
                        rowData={rowData}
                        columnDefs={columnDefs}
                        defaultColDef={defaultColDef}
                        rowSelection="multiple"
                        enableRangeSelection={false}
                        enableCellTextSelection={true}
                        suppressMenuHide={true}
                        animateRows={true}
                        theme={gridTheme}
                        context={{ handleSyncToggle }}
                    />
                </div>
            </Paper>
        </Stack>
    );
}
