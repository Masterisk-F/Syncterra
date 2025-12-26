import { useState, useMemo, useEffect, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ValueFormatterParams, GridApi, GridReadyEvent, IRowNode, ICellRendererParams, CellStyle } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule, themeQuartz, colorSchemeDarkBlue } from 'ag-grid-community';
import { Title, Paper, Stack, useMantineColorScheme, Button, Group, Loader, Text, Badge } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconRefresh, IconDeviceFloppy } from '@tabler/icons-react';
import type { Track } from '../../types/track';
import { getTracks, batchUpdateTracks } from '../../api';
import type { Track as ApiTrack } from '../../api/types';
import { useSync } from '../sync/SyncContext';

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

// 日時フォーマット (YYYY-MM-DD HH:mm:ss)
const formatDate = (dateStr: string): string => {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        return date.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    } catch {
        return dateStr;
    }
};

export default function AudioListPage() {
    const [rowData, setRowData] = useState<Track[]>([]);
    const [loading, setLoading] = useState(true);
    const { colorScheme } = useMantineColorScheme();

    const { isSyncing, isScanning, isConnected, handleScan, lastUpdateId } = useSync();

    const gridTheme = useMemo(() => {
        return colorScheme === 'dark'
            ? themeQuartz.withPart(colorSchemeDarkBlue)
            : themeQuartz;
    }, [colorScheme]);


    // Load tracks from API
    const loadTracks = useCallback(async () => {
        try {
            const tracks: ApiTrack[] = await getTracks();
            // APIのTrack型をフロント型に変換
            const frontendTracks: Track[] = tracks.map((t: ApiTrack) => ({
                id: t.id,
                msg: t.missing ? '!' : (t.msg ?? ''),
                sync: t.sync,
                title: t.title || '',
                artist: t.artist || '',
                album_artist: t.album_artist || '',
                composer: t.composer || '',
                album: t.album || '',
                track_num: t.track_num || '',
                length: t.duration || 0,
                file_name: t.file_name,
                file_path: t.file_path,
                file_path_to_relative: t.relative_path || '',
                codec: t.codec || '',
                size: 0,
                added_date: t.added_date || '',
                update_date: t.last_modified || '',
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
    }, []);

    useEffect(() => {
        loadTracks();
    }, [loadTracks]);

    // リロードフラグ (lastUpdateId) の変更を検知して再読み込み
    useEffect(() => {
        if (lastUpdateId > 0) {
            loadTracks();
        }
    }, [lastUpdateId, loadTracks]);

    // WebSocket初期化はSyncContextに移動しました。

    // Scan実行もSyncContext経由で実行します
    const onScanClick = async () => {
        await handleScan();
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

    const isProcessing = isScanning || isSyncing;

    // Sync Toggle Handler
    const handleSyncToggle = (id: number, currentValue: boolean) => {
        setRowData(prev => prev.map(row =>
            row.id === id ? { ...row, sync: !currentValue } : row
        ));
    };

    // Since we need gridApi for selection, let's refactor slightly to store it
    const [gridApi, setGridApi] = useState<GridApi | null>(null);

    const onGridReady = (params: GridReadyEvent) => {
        setGridApi(params.api);
    };

    // Batch Paste Handler (Ctrl+V)
    const handleContainerPaste = async () => {
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
            const isSelected = selectedNodes.some((node: IRowNode<Track>) => node.data && node.data.id === row.id);
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
            cellStyle: { textAlign: 'center' } as CellStyle,
        },
        {
            field: 'sync',
            headerName: '同期',
            width: 70,
            editable: false,
            cellRenderer: (params: ICellRendererParams) => {
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
            cellStyle: { display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 0 } as CellStyle,
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
            cellStyle: { textAlign: 'center' } as CellStyle,
        },
        {
            field: 'length',
            headerName: '長さ',
            width: 90,
            valueFormatter: (params: ValueFormatterParams) => formatDuration(params.value),
            cellStyle: { textAlign: 'right' } as CellStyle,
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
            valueFormatter: (params: ValueFormatterParams) => formatFileSize(params.value),
            cellStyle: { textAlign: 'right' } as CellStyle,
        },
        {
            field: 'added_date',
            headerName: '追加日時',
            width: 170,
            sortable: true,
            valueFormatter: (params: ValueFormatterParams) => formatDate(params.value),
        },
        {
            field: 'update_date',
            headerName: '更新日時',
            width: 170,
            sortable: true,
            valueFormatter: (params: ValueFormatterParams) => formatDate(params.value),
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
                            onClick={onScanClick}
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
                    </Group>
                </Group>
            </Paper>


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
