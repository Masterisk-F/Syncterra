import { apiClient } from './client';
import type { Setting, Track, TrackUpdate } from './types';

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

// System API

export const scanFiles = async (): Promise<void> => {
    await apiClient.post('/api/scan');
};

export const syncFiles = async (): Promise<void> => {
    await apiClient.post('/api/sync');
};
