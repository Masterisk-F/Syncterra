// OpenAPI仕様から生成された型定義

export interface Setting {
  key: string;
  value: string;
}

export interface Track {
  id: number;
  file_path: string;
  file_name: string;
  title: string | null;
  artist: string | null;
  album: string | null;
  sync: boolean;
  relative_path: string | null;
  msg: string | null;
  missing?: boolean;
  // New fields
  album_artist: string | null;
  composer: string | null;
  track_num: string | null;
  duration: number | null;
  codec: string | null;
  size: number | null;
  added_date: string | null;
  last_modified: string | null;
}

export interface TrackUpdate {
  sync?: boolean | null;
}

export interface BatchTrackUpdate {
  ids: number[];
  sync: boolean;
}

// API レスポンス型
export interface ApiResponse<T> {
  data: T;
  status: number;
}

export interface ApiError {
  detail?: {
    loc: (string | number)[];
    msg: string;
    type: string;
  }[];
  message?: string;
}

// プレイリスト関連の型定義

export interface TrackInPlaylist {
  id: number;
  track_id: number;
  order: number;
  title: string | null;
  artist: string | null;
  file_name: string;
  // New fields
  album: string | null;
  album_artist: string | null;
  composer: string | null;
  track_num: string | null;
  duration: number | null;
  codec: string | null;
  added_date: string | null; // API sends string (ISO format)
  last_modified: string | null;
}

export interface Playlist {
  id: number;
  name: string;
  tracks: TrackInPlaylist[];
}

export interface PlaylistCreate {
  name: string;
}

export interface PlaylistUpdate {
  name?: string | null;
}

export interface PlaylistTracksUpdate {
  track_ids: number[];
}
