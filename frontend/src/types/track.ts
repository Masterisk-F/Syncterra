export interface Track {
  id: number;
  msg: string | null;
  sync: boolean;
  title: string;
  artist: string;
  album_artist: string;
  composer: string;
  album: string;
  track_num: string;
  length: number; // seconds
  file_name: string;
  file_path: string;
  file_path_to_relative: string;
  codec: string;
  size: number; // bytes
  added_date: string;
  update_date: string;
}
