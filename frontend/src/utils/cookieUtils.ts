import Cookies from 'js-cookie';

export const VALID_SORT_BY = ['name', 'artist', 'added', 'updated'] as const;
export const VALID_SORT_ORDER = ['asc', 'desc'] as const;
export const VALID_TRACK_SORT_FIELDS = [
  'id', 'file_path', 'file_name', 'title', 'artist', 'album', 'sync',
  'relative_path', 'msg', 'missing', 'album_artist', 'composer',
  'track_num', 'duration', 'codec', 'size', 'added_date', 'last_modified'
] as const;

export function getValidatedCookie<T extends string>(
  cookieName: string,
  validValues: readonly T[],
  defaultValue: T
): T {
  const val = Cookies.get(cookieName) as T | undefined;
  return val !== undefined && (validValues as readonly string[]).includes(val) ? val : defaultValue;
}
