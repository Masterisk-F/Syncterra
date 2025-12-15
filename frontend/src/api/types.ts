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
