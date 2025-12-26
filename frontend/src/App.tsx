import { AppShell, Burger, Group, NavLink, Title, useMantineColorScheme, ActionIcon, Button } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconMusic, IconSettings, IconSun, IconMoon, IconPlaylist, IconPlayerPlay, IconTerminal2 } from '@tabler/icons-react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';

import SettingsPage from './features/settings/SettingsPage';
import AudioListPage from './features/audio-list/AudioListPage';
import PlaylistPage from './features/playlists/PlaylistPage';
import { SyncProvider, useSync } from './features/sync/SyncContext';
import ProcessLogDrawer from './features/audio-list/ProcessLogDrawer';

function AppContent() {
  const [opened, { toggle }] = useDisclosure();
  const navigate = useNavigate();
  const location = useLocation();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const { handleSync, isSyncing, isScanning, isLogDrawerOpen, setIsLogDrawerOpen, progress, logs, processName } = useSync();

  const isProcessing = isSyncing || isScanning;

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: opened ? 300 : 80,
        breakpoint: 'sm',
      }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} size="sm" />
            <Title order={3}>Syncterra</Title>

            <Group ml="xl" gap="xs">
              <Button
                leftSection={<IconPlayerPlay size={18} />}
                onClick={() => handleSync()}
                loading={isSyncing}
                disabled={isScanning}
                color="green"
                size="xs"
                variant="filled"
              >
                同期実行
              </Button>
              <Button
                leftSection={<IconTerminal2 size={18} />}
                onClick={() => setIsLogDrawerOpen(true)}
                variant="subtle"
                size="xs"
                color="gray"
              >
                ログ
              </Button>
            </Group>
          </Group>
          <ActionIcon
            onClick={() => toggleColorScheme()}
            variant="default"
            size="lg"
            aria-label="Toggle color scheme"
          >
            {colorScheme === 'dark' ? <IconSun stroke={1.5} /> : <IconMoon stroke={1.5} />}
          </ActionIcon>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <NavLink
          label={opened ? "Audio List" : null}
          leftSection={<IconMusic size="1.5rem" stroke={1.5} />}
          active={location.pathname === '/'}
          onClick={() => navigate('/')}
        />
        <NavLink
          label={opened ? "Playlists" : null}
          leftSection={<IconPlaylist size="1.5rem" stroke={1.5} />}
          active={location.pathname === '/playlists'}
          onClick={() => navigate('/playlists')}
        />
        <NavLink
          label={opened ? "Settings" : null}
          leftSection={<IconSettings size="1.5rem" stroke={1.5} />}
          active={location.pathname === '/settings'}
          onClick={() => navigate('/settings')}
        />
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<AudioListPage />} />
          <Route path="/playlists" element={<PlaylistPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </AppShell.Main>

      <ProcessLogDrawer
        opened={isLogDrawerOpen}
        onClose={() => setIsLogDrawerOpen(false)}
        isProcessing={isProcessing}
        processName={processName}
        progress={progress}
        logs={logs}
      />
    </AppShell>
  );
}

export default function App() {
  return (
    <SyncProvider>
      <AppContent />
    </SyncProvider>
  );
}
