import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconRefresh, IconDeviceFloppy, IconSortAscending, IconSortDescending } from '@tabler/icons-react';
import { getTracks, batchUpdateTracks, getAlbumArtUrl } from '../../api';
import type { Track } from '../../api/types';
import { useSync } from '../sync/SyncContext';
import TrackDataGrid from './TrackDataGrid';
import { List, type RowComponentProps, type ListImperativeAPI } from 'react-window';

// Row constants
const ROW_SPACING = 15; // グリッド行間のスペース
const TEXT_AREA_HEIGHT = 75; // テキストエリアの固定高さ（アルバム名・アーティスト・曲数）
const CARD_PADDING = 8; // Card のpadding
const SIMPLE_GRID_SPACING = 16; // SimpleGrid のspacing="md"はデフォルト16px
const HEADER_HEIGHT = 48; // AG Grid header height
const ROW_HEIGHT = 42; // AG Grid row height
const GRID_PADDING = 34; // Paper padding + borders

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

interface AlbumData {
  name: string;
  artist: string;
  count: number;
  tracks: Track[];
  latestAdded: string; // ISO date string
  latestModified: string; // ISO date string
}

type SortBy = 'name' | 'artist' | 'added' | 'updated';
type SortOrder = 'asc' | 'desc';

export default function AudioListPage() {
  const [rowData, setRowData] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);

  // View Mode: 'tracks' or 'albums'
  const [viewMode, setViewMode] = useState<string>('tracks');
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null);

  // Sort State
  const [sortBy, setSortBy] = useState<SortBy>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

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
          tracks: [],
          latestAdded: '',
          latestModified: '',
        });
      }

      const album = map.get(albumName)!;
      album.count++;
      album.tracks.push(track);

      // Update latest dates
      if (track.added_date && (!album.latestAdded || track.added_date > album.latestAdded)) {
        album.latestAdded = track.added_date;
      }
      if (track.last_modified && (!album.latestModified || track.last_modified > album.latestModified)) {
        album.latestModified = track.last_modified;
      }
    });

    const albumList = Array.from(map.values());

    // Sort albums
    return albumList.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'artist':
          comparison = a.artist.localeCompare(b.artist);
          break;
        case 'added':
          // Handle empty dates (treat as oldest)
          if (!a.latestAdded && !b.latestAdded) comparison = 0;
          else if (!a.latestAdded) comparison = -1;
          else if (!b.latestAdded) comparison = 1;
          else comparison = a.latestAdded.localeCompare(b.latestAdded);
          break;
        case 'updated':
          // Handle empty dates (treat as oldest)
          if (!a.latestModified && !b.latestModified) comparison = 0;
          else if (!a.latestModified) comparison = -1;
          else if (!b.latestModified) comparison = 1;
          else comparison = a.latestModified.localeCompare(b.latestModified);
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [rowData, sortBy, sortOrder]);


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

          <Group>
            {viewMode === 'albums' && (
              <Group gap="xs">
                <Select
                  data={[
                    { value: 'name', label: 'アルバム名' },
                    { value: 'artist', label: 'アーティスト名' },
                    { value: 'added', label: '追加日時' },
                    { value: 'updated', label: '更新日時' },
                  ]}
                  value={sortBy}
                  onChange={(val) => setSortBy(val as SortBy)}
                  w={150}
                  allowDeselect={false}
                />
                <Tooltip label={sortOrder === 'asc' ? '昇順 (クリックで降順へ)' : '降順 (クリックで昇順へ)'}>
                  <ActionIcon
                    variant="default"
                    size="lg"
                    onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
                  >
                    {sortOrder === 'asc' ? <IconSortAscending size={20} /> : <IconSortDescending size={20} />}
                  </ActionIcon>
                </Tooltip>
              </Group>
            )}

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
        </Group>
      </Paper>

      <Paper
        withBorder
        radius="md"
        style={{
          height: viewMode === 'tracks' ? 'calc(100vh - 180px)' : undefined,
          display: 'flex',
          flexDirection: 'column',
          overflow: viewMode === 'albums' ? 'visible' : 'hidden',
          backgroundColor: viewMode === 'albums' ? 'transparent' : undefined,
          padding: 0,
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
          <div style={{ flex: 1, width: '100%' }}>
            <AlbumList
              albums={albums}
              cols={cols}
              selectedAlbum={selectedAlbum}
              handleAlbumClick={handleAlbumClick}
              handleSyncToggle={handleSyncToggle}
              handleContainerPaste={handleContainerPaste}
            />
          </div>
        )}

      </Paper>
    </Stack>
  );
}

// Separate component for List to handle ref and resizing

// Separate component for List to handle ref and resizing
interface AlbumListProps {
  albums: AlbumData[];
  cols: number;
  selectedAlbum: string | null;
  handleAlbumClick: (name: string) => void;
  handleSyncToggle: (id: number, val: boolean) => void;
  handleContainerPaste: () => void;
}


const AlbumList = ({
  albums,
  cols,
  selectedAlbum,
  handleAlbumClick,
  handleSyncToggle,
  handleContainerPaste
}: AlbumListProps) => {
  const listRef = useRef<ListImperativeAPI>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [listHeight, setListHeight] = useState(400); // 初期値

  // コンテナ幅とリスト高さを監視
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateDimensions = () => {
      setContainerWidth(container.clientWidth);
      // コンテナのoffsetTopから、ウィンドウ全体の残りの高さを計算
      const rect = container.getBoundingClientRect();
      const availableHeight = window.innerHeight - rect.top - 16; // 16px は下部余白
      setListHeight(Math.max(200, availableHeight)); // 最小200px
    };

    updateDimensions();
    const resizeObserver = new ResizeObserver(updateDimensions);
    resizeObserver.observe(container);
    window.addEventListener('resize', updateDimensions);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateDimensions);
    };
  }, []);

  // カード幅から動的にカード高さを計算
  // カード幅 = (コンテナ幅 - パディング - (cols-1)*spacing) / cols
  // カード高さ = カード幅(正方形アルバムアート) + テキストエリア + padding*2 + mt(4px)
  const calculatedCardHeight = useMemo(() => {
    if (containerWidth === 0) return 300; // 初期値
    const padding = 8; // SimpleGrid p="xs"
    const cardWidth = (containerWidth - padding * 2 - (cols - 1) * SIMPLE_GRID_SPACING) / cols;
    // アルバムアート(正方形) + テキストエリア + Cardのpadding(上下*2) + mt(4px)
    return cardWidth + TEXT_AREA_HEIGHT + CARD_PADDING * 2 + 4;
  }, [containerWidth, cols]);

  // Memoize chunks
  const albumChunks = useMemo(() => {
    const chunks: AlbumData[][] = [];
    for (let i = 0; i < albums.length; i += cols) {
      chunks.push(albums.slice(i, i + cols));
    }
    return chunks;
  }, [albums, cols]);

  // Find which chunk contains the selected album
  const { expandedChunkIndex, selectedAlbumData } = useMemo(() => {
    if (!selectedAlbum) return { expandedChunkIndex: -1, selectedAlbumData: null };

    // Optimization: Depending on how albums are sorted, we might binary search, 
    // but findIndex is O(N/cols) which is fast enough for <10k albums
    const index = albumChunks.findIndex(chunk =>
      chunk.some(a => a.name === selectedAlbum)
    );

    if (index === -1) return { expandedChunkIndex: -1, selectedAlbumData: null };

    const data = albumChunks[index].find(a => a.name === selectedAlbum) || null;
    return { expandedChunkIndex: index, selectedAlbumData: data };
  }, [selectedAlbum, albumChunks]);

  // Calculate detail row height in advance
  const detailRowHeight = useMemo(() => {
    if (!selectedAlbumData) return 0;
    const trackCount = selectedAlbumData.tracks.length;
    // Header + Rows + Padding + Extra
    // Note: TRACK_GRID_EXTRA might need adjustment if it was including card height in previous logic
    const gridHeight = HEADER_HEIGHT + (trackCount * ROW_HEIGHT) + GRID_PADDING;
    return gridHeight + 50; // 50px buffer
  }, [selectedAlbumData]);

  // Total rows = chunks + (1 if expanded)
  const rowCount = albumChunks.length + (expandedChunkIndex !== -1 ? 1 : 0);

  // Helper to map virtual row index to actual chunk index
  // If expandedChunkIndex is 5:
  // Row 0..5 -> Chunk 0..5
  // Row 6 -> Detail Row
  // Row 7..N -> Chunk 6..(N-1)
  const getChunkIndex = useCallback((rowIndex: number) => {
    if (expandedChunkIndex === -1) return rowIndex;
    if (rowIndex <= expandedChunkIndex) return rowIndex;
    if (rowIndex === expandedChunkIndex + 1) return -1; // Special Detail Row
    return rowIndex - 1;
  }, [expandedChunkIndex]);

  // Track previous state for scroll adjustment
  const prevExpandedRef = useRef(-1);
  const prevDetailHeightRef = useRef(0);

  // Adjust scroll position when an album above the newly selected one collapses
  useEffect(() => {
    if (
      listRef.current &&
      listRef.current.element &&
      expandedChunkIndex !== -1 &&
      prevExpandedRef.current !== -1 &&
      prevExpandedRef.current < expandedChunkIndex
    ) {
      // The previously expanded album was above the new one.
      // Its collapse caused the new album to shift up by 'prevDetailHeight'.
      // We compensate by scrolling up (subtracting from scrollTop) by that amount.
      listRef.current.element.scrollTop -= prevDetailHeightRef.current;
    }

    prevExpandedRef.current = expandedChunkIndex;
    prevDetailHeightRef.current = detailRowHeight;
  }, [expandedChunkIndex, detailRowHeight]);

  // Note: react-window v2ではrowHeightに関数を渡すと、関数の参照が変わると自動的に再計算される
  // calculatedCardHeightが変わるとgetItemSizeの参照も変わるため、Listは自動的に再レンダリングされる

  // O(1) size calculation（動的カード高さを使用）
  const getItemSize = useCallback((index: number) => {
    if (expandedChunkIndex !== -1 && index === expandedChunkIndex + 1) {
      return detailRowHeight;
    }
    return calculatedCardHeight + ROW_SPACING;
  }, [expandedChunkIndex, detailRowHeight, calculatedCardHeight]);

  const Row = ({ index, style }: RowComponentProps) => {
    // Check if this is the detail row
    if (expandedChunkIndex !== -1 && index === expandedChunkIndex + 1) {
      if (!selectedAlbumData) return <div style={style} />;
      return (
        <div style={style}>
          <div style={{ paddingLeft: 16, paddingRight: 16, paddingBottom: 16, height: '100%' }}>
            <Paper
              withBorder
              shadow="md"
              p="xs"
              radius="md"
              style={{
                borderColor: 'var(--mantine-primary-color-filled)',
                height: '100%',
                overflow: 'hidden'
              }}
            >
              {/* Prevent click propagation so it doesn't close the album when clicking grid background */}
              <div
                tabIndex={0}
                onPaste={handleContainerPaste}
                style={{ height: '100%' }}
                onClick={(e) => e.stopPropagation()}
              >
                <TrackDataGrid
                  tracks={selectedAlbumData.tracks}
                  onGridReady={() => { }}
                  onSyncToggle={handleSyncToggle}
                  showSelectionCheckbox={false}
                  // Use fixed height or 100% to fill the row
                  domLayout='normal'
                />
              </div>
            </Paper>
          </div>
        </div>
      );
    }

    const chunkIndex = getChunkIndex(index);
    const chunk = albumChunks[chunkIndex];
    if (!chunk) return <div style={style} />;

    return (
      <div style={style}>
        <SimpleGrid cols={cols} spacing="md" p="xs">
          {chunk.map((album) => (
            <Card
              key={album.name}
              shadow="sm"
              padding={8}
              radius={0}
              withBorder
              style={{
                cursor: 'pointer',
                borderColor: selectedAlbum === album.name ? 'var(--mantine-primary-color-filled)' : undefined,
                borderWidth: selectedAlbum === album.name ? 2 : 1,
                // カード全体の高さは固定しない（アルバムアートのサイズに応じて変化）
              }}
              onClick={() => handleAlbumClick(album.name)}
            >
              {/* アルバムアートは常に正方形 */}
              <Card.Section>
                <AspectRatio ratio={1}>
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

              {/* テキストエリアは固定の高さ（75px） */}
              <Stack gap={2} mt={4} style={{ height: 75, flexShrink: 0 }}>
                <Text fw={500} size="sm" lineClamp={2} title={album.name} lh={1.2} style={{ height: 34 }}>
                  {album.name}
                </Text>

                <div style={{ marginTop: 'auto' }}>
                  <Text size="xs" c="dimmed" lineClamp={1} title={album.artist}>
                    {album.artist}
                  </Text>
                  <Badge color="blue" variant="light" size="xs" w="fit-content" mt={2}>
                    {album.count} songs
                  </Badge>
                </div>
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      </div>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <List
        listRef={listRef}
        style={{
          height: listHeight,
          width: '100%'
        }}
        rowCount={rowCount}
        rowHeight={getItemSize}
        rowComponent={Row}
        rowProps={{}}
      />
    </div>
  );
};
