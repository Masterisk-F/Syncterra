import { useState, useEffect } from 'react';
import {
    TextInput,
    TagsInput,
    Select,
    Button,
    Paper,
    Title,
    Stack,
    Group,
    Text,
    Divider,
    NumberInput,
    PasswordInput,
    Switch,
    Alert,
    Loader
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconDeviceFloppy, IconDownload, IconInfoCircle } from '@tabler/icons-react';
import type { AppSettings, SyncMethod } from '../../types/settings';
import { DEFAULT_SETTINGS } from '../../types/settings';
import { getSettings, updateSetting } from '../../api';
import { apiClient } from '../../api/client';
import type { Setting } from '../../api/types';

// バックエンドの設定キーマッピング
const SETTING_KEYS = {
    scanPaths: 'scan_paths',
    excludeDirs: 'exclude_dirs',
    targetExtensions: 'target_exts',
    syncDestPath: 'sync_dest',
    syncMethod: 'sync_mode',
    ftpHost: 'ftp_host',
    ftpPort: 'ftp_port',
    ftpUser: 'ftp_user',
    ftpPassword: 'ftp_pass',
    rsyncHost: 'rsync_host',
    rsyncPort: 'rsync_port',
    rsyncUser: 'rsync_user',
    rsyncPassword: 'rsync_pass',
    rsyncUseKey: 'rsync_use_key',
} as const;

// Setting[] を AppSettings に変換
const settingsArrayToApp = (settings: Setting[]): AppSettings => {
    const settingsMap = new Map(settings.map(s => [s.key, s.value]));

    const parseScanPaths = (val?: string): string[] => {
        if (!val) return [];
        try {
            const parsed = JSON.parse(val);
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    };

    const parseStringArray = (val?: string): string[] => {
        if (!val) return [];
        return val.split(',').map(s => s.trim()).filter(Boolean);
    };

    return {
        scanPaths: parseScanPaths(settingsMap.get(SETTING_KEYS.scanPaths)),
        excludeDirs: parseStringArray(settingsMap.get(SETTING_KEYS.excludeDirs)),
        targetExtensions: parseStringArray(settingsMap.get(SETTING_KEYS.targetExtensions)) || DEFAULT_SETTINGS.targetExtensions,
        syncDestPath: settingsMap.get(SETTING_KEYS.syncDestPath) || '',
        syncMethod: (settingsMap.get(SETTING_KEYS.syncMethod) || 'adb') as SyncMethod,
        ftpHost: settingsMap.get(SETTING_KEYS.ftpHost),
        ftpPort: settingsMap.get(SETTING_KEYS.ftpPort) ? Number(settingsMap.get(SETTING_KEYS.ftpPort)) : 21,
        ftpUser: settingsMap.get(SETTING_KEYS.ftpUser),
        ftpPassword: settingsMap.get(SETTING_KEYS.ftpPassword),
        rsyncHost: settingsMap.get(SETTING_KEYS.rsyncHost),
        rsyncPort: settingsMap.get(SETTING_KEYS.rsyncPort) ? Number(settingsMap.get(SETTING_KEYS.rsyncPort)) : 22,
        rsyncUser: settingsMap.get(SETTING_KEYS.rsyncUser),
        rsyncPassword: settingsMap.get(SETTING_KEYS.rsyncPassword),
        rsyncUseKey: settingsMap.get(SETTING_KEYS.rsyncUseKey) === '1',
    };
};

export default function SettingsPage() {
    const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
    const [loading, setLoading] = useState(false);
    const [initialLoading, setInitialLoading] = useState(true);

    // Load settings from API
    useEffect(() => {
        const loadSettings = async () => {
            try {
                const apiSettings = await getSettings();
                setSettings(settingsArrayToApp(apiSettings));
            } catch (error) {
                console.error('Failed to load settings:', error);
                notifications.show({
                    title: 'エラー',
                    message: '設定の読み込みに失敗しました',
                    color: 'red',
                });
            } finally {
                setInitialLoading(false);
            }
        };
        loadSettings();
    }, []);

    const handleSave = async () => {
        setLoading(true);
        try {
            // 各設定をバックエンドに送信
            await updateSetting(SETTING_KEYS.scanPaths, JSON.stringify(settings.scanPaths));
            await updateSetting(SETTING_KEYS.excludeDirs, settings.excludeDirs.join(','));
            await updateSetting(SETTING_KEYS.targetExtensions, settings.targetExtensions.join(','));
            await updateSetting(SETTING_KEYS.syncDestPath, settings.syncDestPath);
            await updateSetting(SETTING_KEYS.syncMethod, settings.syncMethod);

            if (settings.ftpHost) await updateSetting(SETTING_KEYS.ftpHost, settings.ftpHost);
            if (settings.ftpPort) await updateSetting(SETTING_KEYS.ftpPort, String(settings.ftpPort));
            if (settings.ftpUser) await updateSetting(SETTING_KEYS.ftpUser, settings.ftpUser);
            if (settings.ftpPassword) await updateSetting(SETTING_KEYS.ftpPassword, settings.ftpPassword);

            if (settings.rsyncHost) await updateSetting(SETTING_KEYS.rsyncHost, settings.rsyncHost);
            if (settings.rsyncPort) await updateSetting(SETTING_KEYS.rsyncPort, String(settings.rsyncPort));
            if (settings.rsyncUser) await updateSetting(SETTING_KEYS.rsyncUser, settings.rsyncUser);
            if (settings.rsyncPassword) await updateSetting(SETTING_KEYS.rsyncPassword, settings.rsyncPassword);
            await updateSetting(SETTING_KEYS.rsyncUseKey, settings.rsyncUseKey ? '1' : '0');

            notifications.show({
                title: '成功',
                message: '設定を保存しました',
                color: 'green',
            });
        } catch (error) {
            console.error('Failed to save settings:', error);
            notifications.show({
                title: 'エラー',
                message: '設定の保存に失敗しました',
                color: 'red',
            });
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadSshKey = async () => {
        try {
            // 公開鍵取得API呼び出し（存在しない場合は自動生成される）
            const response = await apiClient.get('/api/settings/ssh-key/public', {
                responseType: 'blob'
            });

            // 公開鍵をダウンロード
            const blob = response.data;
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'audiosync_rsa.pub';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            notifications.show({
                title: '公開鍵をダウンロードしました',
                message: '同期先マシンの ~/.ssh/authorized_keys に追記してください',
                color: 'blue',
            });
        } catch (error) {
            console.error('SSH key retrieval failed:', error);
            notifications.show({
                title: 'エラー',
                message: 'SSH鍵の取得に失敗しました',
                color: 'red',
            });
        }
    };

    if (initialLoading) {
        return (
            <Stack align="center" justify="center" h={400}>
                <Loader size="lg" />
                <Text c="dimmed">設定を読み込み中...</Text>
            </Stack>
        );
    }

    return (
        <Stack gap="lg" maw={800}>
            <Group justify="space-between" align="center">
                <Title order={2}>設定</Title>
                <Button
                    leftSection={<IconDeviceFloppy size={20} />}
                    onClick={handleSave}
                    loading={loading}
                >
                    変更を保存
                </Button>
            </Group>

            <Paper p="md" withBorder radius="md">
                <Stack gap="md">
                    <Text fw={500} size="lg">スキャン設定</Text>
                    <Divider />

                    <TagsInput
                        label="音楽ファイルディレクトリ"
                        description="音楽ファイルが保存されているディレクトリの絶対パス（Enterキーで複数追加可能）"
                        placeholder="/home/user/Music"
                        value={settings.scanPaths}
                        onChange={(value) => setSettings({ ...settings, scanPaths: value })}
                        required
                    />

                    <TagsInput
                        label="除外ディレクトリ"
                        description="スキャンから除外するフォルダ名（Enterキーで追加）"
                        placeholder="フォルダ名を入力"
                        value={settings.excludeDirs}
                        onChange={(value) => setSettings({ ...settings, excludeDirs: value })}
                    />

                    <TagsInput
                        label="対象拡張子"
                        description="スキャン対象とするファイル拡張子"
                        placeholder="mp3"
                        value={settings.targetExtensions}
                        onChange={(value) => setSettings({ ...settings, targetExtensions: value })}
                    />
                </Stack>
            </Paper>

            <Paper p="md" withBorder radius="md">
                <Stack gap="md">
                    <Text fw={500} size="lg">同期設定</Text>
                    <Divider />

                    <Select
                        label="同期方式"
                        description="ファイルの転送方法を選択"
                        data={[
                            { value: 'adb', label: 'ADB (Android USB接続)' },
                            { value: 'ftp', label: 'FTP サーバー' },
                            { value: 'rsync', label: 'Rsync (SSH)' },
                        ]}
                        value={settings.syncMethod}
                        onChange={(value) => setSettings({ ...settings, syncMethod: value as SyncMethod })}
                    />

                    <TextInput
                        label="転送先ディレクトリ"
                        description="デバイス/サーバー上のパス"
                        placeholder="/storage/emulated/0/Music"
                        value={settings.syncDestPath}
                        onChange={(e) => setSettings({ ...settings, syncDestPath: e.target.value })}
                        required
                    />

                    {/* FTP specific settings */}
                    {settings.syncMethod === 'ftp' && (
                        <>
                            <Divider label="FTP接続設定" />
                            <TextInput
                                label="IPアドレス / ホスト名"
                                placeholder="192.168.1.100"
                                value={settings.ftpHost || ''}
                                onChange={(e) => setSettings({ ...settings, ftpHost: e.target.value })}
                                required
                            />
                            <NumberInput
                                label="ポート番号"
                                placeholder="21"
                                value={settings.ftpPort || 21}
                                onChange={(value) => setSettings({ ...settings, ftpPort: Number(value) })}
                                min={1}
                                max={65535}
                            />
                            <TextInput
                                label="ユーザー名"
                                placeholder="ftpuser"
                                value={settings.ftpUser || ''}
                                onChange={(e) => setSettings({ ...settings, ftpUser: e.target.value })}
                                required
                            />
                            <PasswordInput
                                label="パスワード"
                                placeholder="パスワードを入力"
                                value={settings.ftpPassword || ''}
                                onChange={(e) => setSettings({ ...settings, ftpPassword: e.target.value })}
                                required
                            />
                        </>
                    )}

                    {/* Rsync specific settings */}
                    {settings.syncMethod === 'rsync' && (
                        <>
                            <Divider label="SSH/Rsync接続設定" />
                            <TextInput
                                label="IPアドレス / ホスト名"
                                placeholder="192.168.1.100"
                                value={settings.rsyncHost || ''}
                                onChange={(e) => setSettings({ ...settings, rsyncHost: e.target.value })}
                                required
                            />
                            <NumberInput
                                label="SSHポート番号"
                                placeholder="22"
                                value={settings.rsyncPort || 22}
                                onChange={(value) => setSettings({ ...settings, rsyncPort: Number(value) })}
                                min={1}
                                max={65535}
                            />
                            <TextInput
                                label="ユーザー名"
                                placeholder="username"
                                value={settings.rsyncUser || ''}
                                onChange={(e) => setSettings({ ...settings, rsyncUser: e.target.value })}
                                required
                            />

                            <Switch
                                label="SSH公開鍵認証を使用"
                                description="パスワード認証ではなく公開鍵認証を使用する"
                                checked={settings.rsyncUseKey || false}
                                onChange={(e) => setSettings({ ...settings, rsyncUseKey: e.currentTarget.checked })}
                            />

                            {settings.rsyncUseKey ? (
                                <>
                                    <Alert icon={<IconInfoCircle />} title="SSH公開鍵認証" color="blue">
                                        公開鍵をダウンロードして、同期先マシンの <code>~/.ssh/authorized_keys</code> に追記してください。
                                    </Alert>
                                    <Button
                                        leftSection={<IconDownload size={20} />}
                                        onClick={handleDownloadSshKey}
                                        variant="light"
                                    >
                                        SSH公開鍵をダウンロード
                                    </Button>
                                </>
                            ) : (
                                <PasswordInput
                                    label="パスワード"
                                    placeholder="パスワードを入力"
                                    value={settings.rsyncPassword || ''}
                                    onChange={(e) => setSettings({ ...settings, rsyncPassword: e.target.value })}
                                    required
                                />
                            )}
                        </>
                    )}
                </Stack>
            </Paper>
        </Stack>
    );
}
