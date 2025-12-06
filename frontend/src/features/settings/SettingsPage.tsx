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
    Alert
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconDeviceFloppy, IconDownload, IconInfoCircle } from '@tabler/icons-react';
import type { AppSettings, SyncMethod } from '../../types/settings';
import { DEFAULT_SETTINGS } from '../../types/settings';

export default function SettingsPage() {
    const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
    const [loading, setLoading] = useState(false);

    // Mock load settings
    useEffect(() => {
        // In a real app, this would fetch from API
        const savedSettings = localStorage.getItem('audioSyncSettings');
        if (savedSettings) {
            setSettings(JSON.parse(savedSettings));
        }
    }, []);

    const handleSave = async () => {
        setLoading(true);
        try {
            // Mock save
            await new Promise(resolve => setTimeout(resolve, 500));
            localStorage.setItem('audioSyncSettings', JSON.stringify(settings));

            notifications.show({
                title: '成功',
                message: '設定を保存しました',
                color: 'green',
            });
        } catch (error) {
            notifications.show({
                title: 'エラー',
                message: '設定の保存に失敗しました',
                color: 'red',
            });
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadSshKey = () => {
        // Mock SSH key generation and download
        const mockPublicKey = `ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDExamplePublicKey audiosync@localhost`;
        const blob = new Blob([mockPublicKey], { type: 'text/plain' });
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
    };

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
