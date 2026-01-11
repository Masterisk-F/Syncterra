import { useState, useEffect, useCallback } from 'react';
import type { GridApi, GridReadyEvent, IRowNode } from 'ag-grid-community';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import {
  Title,
  Paper,
  Stack,
  Button,
  Group,
  Loader,
  Text,
  Badge,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconRefresh, IconDeviceFloppy } from '@tabler/icons-react';
import { getTracks, batchUpdateTracks } from '../../api';
import type { Track } from '../../api/types';
import { useSync } from '../sync/SyncContext';
import TrackDataGrid from './TrackDataGrid';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

export default function AudioListPage() {
  const [rowData, setRowData] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);

  const { isSyncing, isScanning, isConnected, handleScan, lastUpdateId } =
    useSync();

  // Load tracks from API
  const loadTracks = useCallback(async () => {
    try {
      const tracks: Track[] = await getTracks();
      // DB上のmissingフラグをUI用にmsgに変換するなどの処理が必要ならここで行う
      // しかしAPIのTrack型にはmsgとmissing両方あるので、バックエンドが適切に設定していると仮定、
      // またはフロントで加工。元のAudioListPageでは missing ? '!' : (msg??'') だった。
      // 共通型では missing と msg がある。

      // UI表示用に調整
      const formattedTracks = tracks.map((t) => ({
        ...t,
        msg: t.missing ? '!' : (t.msg ?? ''),
      }));

      setRowData(formattedTracks);
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

  const onScanClick = async () => {
    await handleScan();
  };

  // Save Sync Settings - syncフラグをバックエンドに保存
  const handleSaveSync = async () => {
    try {
      const changedTracks = rowData.filter((r) => r.sync);
      if (changedTracks.length > 0) {
        await batchUpdateTracks(
          changedTracks.map((r) => r.id),
          true
        );
      }
      const unchangedTracks = rowData.filter((r) => !r.sync);
      if (unchangedTracks.length > 0) {
        await batchUpdateTracks(
          unchangedTracks.map((r) => r.id),
          false
        );
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
    setRowData((prev) =>
      prev.map((row) => (row.id === id ? { ...row, sync: !currentValue } : row))
    );
  };

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

    const updatedRows = rowData.map((row) => {
      const isSelected = selectedNodes.some(
        (node: IRowNode<Track>) => node.data && node.data.id === row.id
      );
      if (isSelected) {
        return { ...row, sync: newValue };
      }
      return row;
    });

    setRowData(updatedRows);
    notifications.show({
      title: '一括更新',
      message: `${selectedNodes.length}件の同期設定を${newValue ? 'ON' : 'OFF'}にしました`,
      color: 'teal',
    });
  };

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
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            height: '100%',
            width: '100%',
          }}
          onPaste={handleContainerPaste}
          tabIndex={0}
        >
          <TrackDataGrid
            tracks={rowData}
            onGridReady={onGridReady}
            onSyncToggle={handleSyncToggle}
            showSelectionCheckbox={false}
          />
        </div>
      </Paper>
    </Stack>
  );
}
