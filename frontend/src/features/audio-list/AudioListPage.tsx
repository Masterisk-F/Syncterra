import { useState, useEffect, useCallback, useMemo } from 'react';
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
  Select,
  Card,
  Image,
  SimpleGrid,
  AspectRatio,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconRefresh, IconDeviceFloppy } from '@tabler/icons-react';
import { getTracks, batchUpdateTracks, getAlbumArtUrl } from '../../api';
import type { Track } from '../../api/types';
import { useSync } from '../sync/SyncContext';
import TrackDataGrid from './TrackDataGrid';

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

interface AlbumData {
  name: string;
  artist: string;
  count: number;
  tracks: Track[];
}

export default function AudioListPage() {
  const [rowData, setRowData] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);

  // View Mode: 'tracks' or 'albums'
  const [viewMode, setViewMode] = useState<string>('tracks');
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null);

  // Responsive columns for Album Grid
  const isMobile = useMediaQuery('(max-width: 480px)');
  const isTablet = useMediaQuery('(max-width: 768px)');
  const isSmallDesktop = useMediaQuery('(max-width: 1024px)');
  const isMediumDesktop = useMediaQuery('(max-width: 1280px)');
  const isLargeDesktop = useMediaQuery('(max-width: 1536px)');

  const cols = isMobile ? 2 : isTablet ? 3 : isSmallDesktop ? 4 : isMediumDesktop ? 5 : isLargeDesktop ? 6 : 7;

  const { isSyncing, isScanning, isConnected, handleScan, lastUpdateId } =
    useSync();

  // Group tracks by album
  const albums = useMemo(() => {
    const map = new Map<string, AlbumData>();

    rowData.forEach(track => {
      const albumName = track.album || 'Unknown Album';
      if (!map.has(albumName)) {
        // Use album_artist if available, otherwise first artist, or Unknown
        const artist = track.album_artist || track.artist || 'Unknown Artist';
        map.set(albumName, {
          name: albumName,
          artist,
          count: 0,
          tracks: []
        });
      }

      const album = map.get(albumName)!;
      album.count++;
      album.tracks.push(track);
    });

    // Sort albums by name
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [rowData]);

  // Chunk albums for row-based rendering to support inline expansion
  const albumChunks = useMemo(() => {
    const chunks: AlbumData[][] = [];
    for (let i = 0; i < albums.length; i += cols) {
      chunks.push(albums.slice(i, i + cols));
    }
    return chunks;
  }, [albums, cols]);

  const handleAlbumClick = (albumName: string) => {
    setSelectedAlbum(prev => prev === albumName ? null : albumName);
  };

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

          <Select
            data={[
              { value: 'tracks', label: '曲一覧' },
              { value: 'albums', label: 'アルバム一覧' },
            ]}
            value={viewMode}
            onChange={(value) => {
              if (value) {
                setViewMode(value);
                setSelectedAlbum(null);
              }
            }}
            allowDeselect={false}
            w={150}
          />
        </Group>
      </Paper>

      <Paper
        withBorder
        radius="md"
        style={{
          height: viewMode === 'tracks' ? 'calc(100vh - 180px)' : 'auto',
          minHeight: viewMode === 'albums' ? 'calc(100vh - 180px)' : 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: viewMode === 'albums' ? 'visible' : 'hidden',
          backgroundColor: viewMode === 'albums' ? 'transparent' : undefined,
          padding: viewMode === 'albums' ? '1rem' : 0,
          border: viewMode === 'albums' ? 'none' : undefined,
        }}
      >
        {viewMode === 'tracks' ? (
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
        ) : (
          <Stack gap="md">
            {albumChunks.map((chunk, chunkIndex) => {
              // Check if selected album is in this chunk
              const selectedAlbumData = chunk.find(a => a.name === selectedAlbum);

              return (
                <div key={chunkIndex}>
                  <SimpleGrid cols={cols} spacing="md">
                    {chunk.map((album) => (
                      <Card
                        key={album.name}
                        shadow="sm"
                        padding="xs"
                        radius={0}
                        withBorder
                        style={{
                          cursor: 'pointer',
                          borderColor: selectedAlbum === album.name ? 'var(--mantine-primary-color-filled)' : undefined,
                          borderWidth: selectedAlbum === album.name ? 2 : 1
                        }}
                        onClick={() => handleAlbumClick(album.name)}
                      >
                        <Card.Section>
                          <AspectRatio ratio={1 / 1}>
                            <Image
                              src={getAlbumArtUrl(album.name)}
                              w="100%"
                              h="100%"
                              alt={album.name}
                              radius={0}
                              fallbackSrc="https://placehold.co/300x300?text=No+Image"
                            />
                          </AspectRatio>
                        </Card.Section>

                        <Stack gap={2} mt="xs">
                          <Text fw={500} size="sm" lineClamp={2} title={album.name} lh={1.2}>
                            {album.name}
                          </Text>
                          <Text size="xs" c="dimmed" lineClamp={1} title={album.artist}>
                            {album.artist}
                          </Text>
                          <Badge color="blue" variant="light" size="xs" w="fit-content" mt={2}>
                            {album.count} songs
                          </Badge>
                        </Stack>
                      </Card>
                    ))}
                  </SimpleGrid>

                  {/* Inline Expansion Area */}
                  {selectedAlbumData && (
                    <Paper
                      withBorder
                      shadow="md"
                      p="xs"
                      mt="md"
                      mb="md"
                      radius="md"
                      style={{
                        borderColor: 'var(--mantine-primary-color-filled)',
                      }}
                    >

                      {/* 
                         Assuming TrackDataGrid handles its own internal logic for onSyncToggle etc.
                         We use autoHeight as requested.
                      */}
                      <div tabIndex={0} onPaste={handleContainerPaste}> {/* Allow paste on detail grid too */}
                        <TrackDataGrid
                          tracks={selectedAlbumData.tracks}
                          onGridReady={() => { }} // We might not need global gridApi ref for these sub-grids for now
                          onSyncToggle={handleSyncToggle}
                          showSelectionCheckbox={false}
                          domLayout='autoHeight'
                        />
                      </div>
                    </Paper>
                  )}
                </div>
              );
            })}
          </Stack>
        )}

      </Paper>
    </Stack >
  );
}
