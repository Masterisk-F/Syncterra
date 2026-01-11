import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import type { GridApi, IRowNode } from 'ag-grid-community';
import ReactDOM from 'react-dom';
import { notifications } from '@mantine/notifications';
import {
  IconGripVertical,
  IconMusicPlus,
  IconPencil,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import { useState, useEffect } from 'react';
import type { DropResult } from '@hello-pangea/dnd';
import { DragDropContext, Draggable, Droppable } from '@hello-pangea/dnd';

import {
  createPlaylist,
  deletePlaylist,
  getPlaylists,
  getTracks,
  updatePlaylist,
  updatePlaylistTracks,
} from '../../api';
import type { Playlist, Track, TrackInPlaylist } from '../../api/types';
import TrackDataGrid from '../audio-list/TrackDataGrid';

// プレイリスト一覧を読み込み

export default function PlaylistPage() {
  // const { colorScheme } = useMantineColorScheme(); // Unused
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState('');
  const [editingPlaylist, setEditingPlaylist] = useState<Playlist | null>(null);
  const [editedTracks, setEditedTracks] = useState<TrackInPlaylist[]>([]);
  const [addTrackModalOpen, setAddTrackModalOpen] = useState(false);
  const [allTracks, setAllTracks] = useState<Track[]>([]);
  const [gridApi, setGridApi] = useState<GridApi | null>(null);

  // プレイリスト一覧を読み込み
  const loadPlaylists = async () => {
    try {
      const data = await getPlaylists();
      setPlaylists(data);
    } catch (error) {
      console.error('Failed to load playlists:', error);
      notifications.show({
        title: 'エラー',
        message: 'プレイリストの読み込みに失敗しました',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  // 利用可能な曲を読み込み
  const loadAvailableTracks = async () => {
    try {
      const tracks = await getTracks();
      setAllTracks(tracks);
    } catch (error) {
      console.error('Failed to load tracks:', error);
    }
  };

  useEffect(() => {
    loadPlaylists();
    loadAvailableTracks();
  }, []);

  // プレイリスト作成
  const handleCreatePlaylist = async () => {
    if (!newPlaylistName.trim()) {
      notifications.show({
        title: '入力エラー',
        message: 'プレイリスト名を入力してください',
        color: 'red',
      });
      return;
    }

    try {
      await createPlaylist({ name: newPlaylistName });
      notifications.show({
        title: '作成成功',
        message: 'プレイリストを作成しました',
        color: 'green',
      });
      setNewPlaylistName('');
      setCreateModalOpen(false);
      loadPlaylists();
    } catch (error: any) {
      // eslint-disable-line @typescript-eslint/no-explicit-any
      console.error('Failed to create playlist:', error);
      const message =
        error.response?.data?.detail || 'プレイリストの作成に失敗しました';
      notifications.show({
        title: 'エラー',
        message,
        color: 'red',
      });
    }
  };

  // プレイリスト削除
  const handleDeletePlaylist = async (id: number, name: string) => {
    if (!confirm(`プレイリスト "${name}" を削除しますか？`)) {
      return;
    }

    try {
      await deletePlaylist(id);
      notifications.show({
        title: '削除成功',
        message: 'プレイリストを削除しました',
        color: 'green',
      });
      loadPlaylists();
    } catch (error) {
      console.error('Failed to delete playlist:', error);
      notifications.show({
        title: 'エラー',
        message: 'プレイリストの削除に失敗しました',
        color: 'red',
      });
    }
  };

  // プレイリスト編集モーダルを開く
  const handleEditPlaylist = (playlist: Playlist) => {
    setEditingPlaylist(playlist);
    setEditedTracks([...playlist.tracks]);
    setEditModalOpen(true);
  };

  // プレイリスト保存（名前と曲を同時に保存）
  const handleSavePlaylist = async () => {
    if (!editingPlaylist) return;

    try {
      // プレイリスト名を更新
      await updatePlaylist(editingPlaylist.id, { name: editingPlaylist.name });

      // 曲リストを更新
      const trackIds = editedTracks.map((t) => t.track_id);
      await updatePlaylistTracks(editingPlaylist.id, trackIds);

      notifications.show({
        title: '更新成功',
        message: 'プレイリストを更新しました',
        color: 'green',
      });
      setEditModalOpen(false);
      loadPlaylists();
    } catch (error: any) {
      // eslint-disable-line @typescript-eslint/no-explicit-any
      const message =
        error.response?.data?.detail || 'プレイリストの更新に失敗しました';
      notifications.show({
        title: 'エラー',
        message,
        color: 'red',
      });
    }
  };

  // 曲を追加（複数選択から）
  const handleAddTracks = () => {
    if (!gridApi) return;

    const selectedNodes = gridApi.getSelectedNodes();
    if (selectedNodes.length === 0) {
      notifications.show({
        title: '警告',
        message: '曲を選択してください',
        color: 'yellow',
      });
      return;
    }

    const newTracks: TrackInPlaylist[] = [];
    const existingTrackIds = new Set(editedTracks.map((t) => t.track_id));

    selectedNodes.forEach((node: IRowNode<Track>) => {
      const track = node.data;
      if (!track) return;
      // 既に追加済みかチェック
      if (!existingTrackIds.has(track.id)) {
        newTracks.push({
          id: 0,
          track_id: track.id,
          order: editedTracks.length + newTracks.length,
          title: track.title,
          artist: track.artist,
          file_name: track.file_name,
          album: track.album,
          album_artist: track.album_artist,
          composer: track.composer,
          track_num: track.track_num,
          duration: track.duration,
          codec: track.codec,
          added_date: track.added_date,
          last_modified: track.last_modified,
        });
      }
    });

    if (newTracks.length === 0) {
      notifications.show({
        title: '情報',
        message: '選択した曲は既に追加されています',
        color: 'blue',
      });
    } else {
      setEditedTracks([...editedTracks, ...newTracks]);
      notifications.show({
        title: '追加成功',
        message: `${newTracks.length}曲を追加しました`,
        color: 'green',
      });
    }

    setAddTrackModalOpen(false);
  };

  // 曲を削除
  const handleRemoveTrack = (index: number) => {
    const newTracks = editedTracks.filter((_, i) => i !== index);
    // order を再設定
    const reorderedTracks = newTracks.map((t, i) => ({ ...t, order: i }));
    setEditedTracks(reorderedTracks);
  };

  // ドラッグ&ドロップで曲順変更
  const handleDragEnd = (result: DropResult) => {
    if (!result.destination) return;

    const items = Array.from(editedTracks);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);

    // order を再設定
    const reorderedTracks = items.map((t, i) => ({ ...t, order: i }));
    setEditedTracks(reorderedTracks);
  };

  if (loading) {
    return (
      <Stack align="center" justify="center" h={400}>
        <Loader size="lg" />
        <Text c="dimmed">プレイリストを読み込み中...</Text>
      </Stack>
    );
  }

  return (
    <Stack gap="md">
      <Paper p="md" withBorder radius="md">
        <Group justify="space-between" align="center">
          <Title order={2}>プレイリスト</Title>
          <Button
            leftSection={<IconPlus size={20} />}
            onClick={() => setCreateModalOpen(true)}
          >
            新規プレイリスト
          </Button>
        </Group>
      </Paper>

      {playlists.length === 0 ? (
        <Paper p="xl" withBorder radius="md">
          <Stack align="center" gap="sm">
            <Text size="lg" c="dimmed">
              プレイリストがありません
            </Text>
            <Text size="sm" c="dimmed">
              「新規プレイリスト」ボタンから作成してください
            </Text>
          </Stack>
        </Paper>
      ) : (
        <Stack gap="md">
          {playlists.map((playlist) => (
            <Card
              key={playlist.id}
              shadow="sm"
              padding="lg"
              radius="md"
              withBorder
            >
              <Group justify="space-between" mb="md">
                <Group>
                  <Title order={4}>{playlist.name}</Title>
                  <Badge color="blue" variant="light">
                    {playlist.tracks.length} 曲
                  </Badge>
                </Group>
                <Group gap="xs">
                  <ActionIcon
                    variant="light"
                    color="blue"
                    onClick={() => handleEditPlaylist(playlist)}
                  >
                    <IconPencil size={18} />
                  </ActionIcon>
                  <ActionIcon
                    variant="light"
                    color="red"
                    onClick={() =>
                      handleDeletePlaylist(playlist.id, playlist.name)
                    }
                  >
                    <IconTrash size={18} />
                  </ActionIcon>
                </Group>
              </Group>

              {playlist.tracks.length > 0 ? (
                <Stack gap="xs">
                  {playlist.tracks.map((track, index) => (
                    <Group key={track.id} gap="xs">
                      <Text size="sm" c="dimmed" w={30}>
                        {index + 1}.
                      </Text>
                      <Text size="sm">{track.title || track.file_name}</Text>
                      <Text size="sm" c="dimmed">
                        - {track.artist || '不明'}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">
                  曲が登録されていません
                </Text>
              )}
            </Card>
          ))}
        </Stack>
      )}

      {/* 新規作成モーダル */}
      <Modal
        opened={createModalOpen}
        onClose={() => {
          setCreateModalOpen(false);
          setNewPlaylistName('');
        }}
        title="新規プレイリスト作成"
      >
        <Stack gap="md">
          <TextInput
            label="プレイリスト名"
            placeholder="プレイリスト名を入力"
            value={newPlaylistName}
            onChange={(e) => setNewPlaylistName(e.target.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setCreateModalOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={handleCreatePlaylist}>作成</Button>
          </Group>
        </Stack>
      </Modal>

      {/* 編集モーダル */}
      <Modal
        opened={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="プレイリスト編集"
        size="lg"
        styles={{
          body: {
            transform: 'none',
          },
        }}
      >
        <Stack gap="md">
          <TextInput
            label="プレイリスト名"
            value={editingPlaylist?.name || ''}
            onChange={(e) =>
              setEditingPlaylist(
                editingPlaylist
                  ? { ...editingPlaylist, name: e.target.value }
                  : null
              )
            }
          />

          <Stack gap="xs">
            <Group justify="space-between">
              <Text fw={500}>曲リスト</Text>
              <Button
                leftSection={<IconMusicPlus size={18} />}
                onClick={() => setAddTrackModalOpen(true)}
                size="sm"
              >
                曲追加
              </Button>
            </Group>

            <DragDropContext onDragEnd={handleDragEnd}>
              <Droppable droppableId="playlist-tracks">
                {(provided) => (
                  <div {...provided.droppableProps} ref={provided.innerRef}>
                    <Stack gap="xs">
                      {editedTracks.length === 0 ? (
                        <Text size="sm" c="dimmed" ta="center" py="md">
                          曲が登録されていません
                        </Text>
                      ) : (
                        editedTracks.map((track, index) => (
                          <Draggable
                            key={`${track.track_id}-${index}`}
                            draggableId={`${track.track_id}-${index}`}
                            index={index}
                          >
                            {(provided, snapshot) => {
                              const usePortal = snapshot.isDragging;
                              const child = (
                                <Paper
                                  ref={provided.innerRef}
                                  {...provided.draggableProps}
                                  p="xs"
                                  withBorder
                                  style={{
                                    ...provided.draggableProps.style,
                                  }}
                                >
                                  <Group justify="space-between">
                                    <Group gap="xs">
                                      <div {...provided.dragHandleProps}>
                                        <IconGripVertical
                                          size={18}
                                          style={{ cursor: 'grab' }}
                                        />
                                      </div>
                                      <Text size="sm" c="dimmed" w={30}>
                                        {index + 1}.
                                      </Text>
                                      <Text size="sm">
                                        {track.title || track.file_name}
                                      </Text>
                                      <Text size="sm" c="dimmed">
                                        - {track.artist || '不明'}
                                      </Text>
                                    </Group>
                                    <ActionIcon
                                      variant="light"
                                      color="red"
                                      size="sm"
                                      onClick={() => handleRemoveTrack(index)}
                                    >
                                      <IconTrash size={16} />
                                    </ActionIcon>
                                  </Group>
                                </Paper>
                              );

                              if (!usePortal) {
                                return child;
                              }

                              return ReactDOM.createPortal(
                                child,
                                document.body
                              );
                            }}
                          </Draggable>
                        ))
                      )}
                    </Stack>
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </DragDropContext>
          </Stack>

          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEditModalOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={handleSavePlaylist}>保存</Button>
          </Group>
        </Stack>
      </Modal>

      {/* 曲追加モーダル */}
      <Modal
        opened={addTrackModalOpen}
        onClose={() => setAddTrackModalOpen(false)}
        title="曲を追加"
        fullScreen
      >
        <Stack gap="md">
          <Paper
            withBorder
            radius="md"
            style={{
              height: '500px',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{ height: '100%', width: '100%' }}>
              <div style={{ height: '100%', width: '100%' }}>
                <TrackDataGrid
                  onGridReady={(params) => setGridApi(params.api)}
                  tracks={allTracks}
                  readOnlySync={true}
                />
              </div>
            </div>
          </Paper>

          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => setAddTrackModalOpen(false)}
            >
              キャンセル
            </Button>
            <Button onClick={handleAddTracks}>追加</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
