import { apiClient } from './client';
import type { Setting, Track, TrackUpdate, Playlist, PlaylistCreate, PlaylistUpdate, PlaylistTracksUpdate } from './types';
export type { Setting, Track, TrackUpdate, Playlist, PlaylistCreate, PlaylistUpdate, PlaylistTracksUpdate };

// Settings API

export const getSettings = async (): Promise<Setting[]> => {
    const response = await apiClient.get<Setting[]>('/api/settings');
    return response.data;
};

export const updateSetting = async (key: string, value: string): Promise<void> => {
    await apiClient.put('/api/settings', { key, value });
};

// Tracks API

export const getTracks = async (): Promise<Track[]> => {
    const response = await apiClient.get<Track[]>('/api/tracks');
    return response.data;
};

export const updateTrack = async (id: number, data: TrackUpdate): Promise<void> => {
    await apiClient.put(`/api/tracks/${id}`, data);
};

export const batchUpdateTracks = async (ids: number[], sync: boolean): Promise<void> => {
    await apiClient.put('/api/tracks/batch', { ids, sync });
};

export const deleteMissingTracks = async (): Promise<void> => {
    await apiClient.delete('/api/tracks/missing');
};

// System API

export const scanFiles = async (): Promise<void> => {
    await apiClient.post('/api/scan');
};

export const syncFiles = async (): Promise<void> => {
    await apiClient.post('/api/sync');
};

// Playlists API

export const getPlaylists = async (): Promise<Playlist[]> => {
    const response = await apiClient.get<Playlist[]>('/api/playlists');
    return response.data;
};

export const getPlaylist = async (id: number): Promise<Playlist> => {
    const response = await apiClient.get<Playlist>(`/api/playlists/${id}`);
    return response.data;
};

export const createPlaylist = async (data: PlaylistCreate): Promise<Playlist> => {
    const response = await apiClient.post<Playlist>('/api/playlists', data);
    return response.data;
};

export const updatePlaylist = async (id: number, data: PlaylistUpdate): Promise<void> => {
    await apiClient.put(`/api/playlists/${id}`, data);
};

export const deletePlaylist = async (id: number): Promise<void> => {
    await apiClient.delete(`/api/playlists/${id}`);
};

export const updatePlaylistTracks = async (id: number, trackIds: number[]): Promise<void> => {
    await apiClient.put(`/api/playlists/${id}/tracks`, { track_ids: trackIds });
};
