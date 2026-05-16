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
import Cookies from 'js-cookie';
import { getValidatedCookie, VALID_SORT_BY, VALID_SORT_ORDER, VALID_TRACK_SORT_FIELDS } from '../../utils/cookieUtils';
import { notifications } from '@mantine/notifications';
import { IconRefresh, IconDeviceFloppy, IconSortAscending, IconSortDescending, IconLayoutGrid, IconList } from '@tabler/icons-react';
import { getTracks, batchUpdateTracks, getAlbumArtUrl, initAlbumArtBaseUrl } from '../../api';
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
const GRID_PADDING = 42; // Paper padding + borders
const ALBUM_INFO_HEIGHT = 30; // アルバム情報ヘッダーの高さ

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

// AlbumRow に rowProps 経由で渡すデータの型
interface AlbumRowData {
  albumChunks: AlbumData[][];
  cols: number;
  selectedAlbum: string | null;
  expandedChunkIndex: number;
  selectedAlbumData: AlbumData | null;
  handleAlbumClick: (name: string) => void;
  handleSyncToggle: (id: number, val: boolean) => void;
  handleContainerPaste: () => void;
  getChunkIndex: (rowIndex: number) => number;
}

// react-window の rowComponent としてトップレベルに定義することで、
// 親コンポーネントの再レンダリング時にコンポーネント型が再生成されるのを防ぐ
const AlbumRow = ({
  index,
  style,
  expandedChunkIndex,
  selectedAlbumData,
  handleContainerPaste,
  handleSyncToggle,
  getChunkIndex,
  albumChunks,
  cols,
  selectedAlbum,
  handleAlbumClick,
}: RowComponentProps<AlbumRowData>) => {
  // 詳細行（トラックリスト）の描画
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
              style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
              onClick={(e) => e.stopPropagation()}
            >
              <Text size="sm" mb={4} pl={4} lineClamp={1} title={`${selectedAlbumData.name} - ${selectedAlbumData.artist}`}>
                <Text span fw={700}>{selectedAlbumData.name}</Text> - {selectedAlbumData.artist}
              </Text>
              <div style={{ flex: 1, minHeight: 0 }}>
                <TrackDataGrid
                  tracks={selectedAlbumData.tracks}
                  onGridReady={() => { }}
                  onSyncToggle={handleSyncToggle}
                  showSelectionCheckbox={false}
                  domLayout='normal'
                />
              </div>
            </div>
          </Paper>
        </div>
      </div>
    );
  }

  // アルバムカード行の描画
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

export default function AudioListPage() {
  const [rowData, setRowData] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);

  // View Mode: 'tracks' or 'albums'
  const [viewMode, setViewMode] = useState<string>('tracks');
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null);

  // Sort State - album list
  const [sortBy, setSortBy] = useState<SortBy>(
    getValidatedCookie('audio-list-sort-by', VALID_SORT_BY, 'name')
  );
  const [sortOrder, setSortOrder] = useState<SortOrder>(
    getValidatedCookie('audio-list-sort-order', VALID_SORT_ORDER, 'asc')
  );

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

    // アルバム内のトラックをトラック番号順にソート
    albumList.forEach(album => {
      album.tracks.sort((a, b) => {
        const parseTrackNum = (numStr: string | null) => {
          if (!numStr) return 9999;
          const match = numStr.match(/^(\d+)/);
          return match ? parseInt(match[1], 10) : 9999;
        };
        return parseTrackNum(a.track_num) - parseTrackNum(b.track_num);
      });
    });

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

  const handleSortByChange = (val: string | null) => {
    if (val) {
      setSortBy(val as SortBy);
      Cookies.set('audio-list-sort-by', val, { expires: 365 });
    }
  };

  const handleSortOrderToggle = () => {
    const newOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    setSortOrder(newOrder);
    Cookies.set('audio-list-sort-order', newOrder, { expires: 365 });
  };

  // Track sort state
  const handleTrackSortChanged = (field: string, order: 'asc' | 'desc') => {
    Cookies.set('audio-list-track-sort-field', field, { expires: 365 });
    Cookies.set('audio-list-track-sort-order', order, { expires: 365 });
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
    // Initialize album art base URL before loading tracks
    initAlbumArtBaseUrl().then(() => loadTracks());
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
                  onChange={handleSortByChange}
                  w={150}
                  allowDeselect={false}
                />
                <Tooltip label={sortOrder === 'asc' ? '昇順 (クリックで降順へ)' : '降順 (クリックで昇順へ)'}>
                  <ActionIcon
                    variant="default"
                    size="lg"
                    onClick={handleSortOrderToggle}
                  >
                    {sortOrder === 'asc' ? <IconSortAscending size={20} /> : <IconSortDescending size={20} />}
                  </ActionIcon>
                </Tooltip>
              </Group>
            )}

            <Group gap="xs">
              <Tooltip label="曲">
                <ActionIcon
                  variant={viewMode === 'tracks' ? 'filled' : 'default'}
                  size="lg"
                  onClick={() => {
                    setViewMode('tracks');
                    setSelectedAlbum(null);
                  }}
                  color={viewMode === 'tracks' ? 'blue' : undefined}
                >
                  <IconList size={20} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label="アルバム">
                <ActionIcon
                  variant={viewMode === 'albums' ? 'filled' : 'default'}
                  size="lg"
                  onClick={() => {
                    setViewMode('albums');
                    setSelectedAlbum(null);
                  }}
                  color={viewMode === 'albums' ? 'blue' : undefined}
                >
                  <IconLayoutGrid size={20} />
                </ActionIcon>
              </Tooltip>
            </Group>
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
              defaultSortField={getValidatedCookie('audio-list-track-sort-field', VALID_TRACK_SORT_FIELDS, 'added_date')}
              defaultSortOrder={getValidatedCookie('audio-list-track-sort-order', VALID_SORT_ORDER, 'desc')}
              onSortChanged={handleTrackSortChanged}
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

  // Calculate scrollbar height (horizontal scrollbar thickness)
  const scrollbarHeight = useMemo(() => {
    if (typeof document === 'undefined') return 0;
    const outer = document.createElement('div');
    outer.style.visibility = 'hidden';
    outer.style.width = '100px';
    outer.style.height = '100px';
    outer.style.overflow = 'scroll';
    document.body.appendChild(outer);
    const height = outer.offsetHeight - outer.clientHeight;
    if (outer.parentNode) outer.parentNode.removeChild(outer);
    return height;
  }, []);

  // Calculate detail row height in advance
  const detailRowHeight = useMemo(() => {
    if (!selectedAlbumData) return 0;
    const trackCount = selectedAlbumData.tracks.length;
    // Header + Rows + Padding + Extra + Album Info Header + Scrollbar Height
    const gridHeight = HEADER_HEIGHT + (trackCount * ROW_HEIGHT) + GRID_PADDING + ALBUM_INFO_HEIGHT + scrollbarHeight;
    return gridHeight;
  }, [selectedAlbumData, scrollbarHeight]);

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

  // rowProps をメモ化して、不要な再レンダリングを防ぐ
  const rowProps = useMemo((): AlbumRowData => ({
    albumChunks,
    cols,
    selectedAlbum,
    expandedChunkIndex,
    selectedAlbumData,
    handleAlbumClick,
    handleSyncToggle,
    handleContainerPaste,
    getChunkIndex,
  }), [albumChunks, cols, selectedAlbum, expandedChunkIndex, selectedAlbumData, handleAlbumClick, handleSyncToggle, handleContainerPaste, getChunkIndex]);

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
        rowComponent={AlbumRow}
        rowProps={rowProps}
      />
    </div>
  );
};
