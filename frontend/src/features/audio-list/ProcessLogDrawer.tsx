import { Drawer, ScrollArea, Stack, Text, Progress, Group, Box } from '@mantine/core';
import { IconTerminal2 } from '@tabler/icons-react';

interface ProcessLogDrawerProps {
    opened: boolean;
    onClose: () => void;
    isProcessing: boolean;
    processName: string; // 'スキャン' or '同期' etc
    progress: number;
    logs: string[];
}

export default function ProcessLogDrawer({
    opened,
    onClose,
    isProcessing,
    processName,
    progress,
    logs
}: ProcessLogDrawerProps) {
    return (
        <Drawer
            opened={opened}
            onClose={onClose}
            title={
                <Group>
                    <IconTerminal2 size={20} />
                    <Text fw={700}>実行ログ - {processName}</Text>
                </Group>
            }
            position="right"
            size="md"
            overlayProps={{ backgroundOpacity: 0.5, blur: 4 }}
        >
            <Stack h="calc(100vh - 80px)" justify="flex-start">
                {/* Progress Section */}
                <Box>
                    <Group justify="space-between" mb={5}>
                        <Text size="sm" fw={500}>
                            {isProcessing ? `${processName}中...` : '待機中 / 完了'}
                        </Text>
                        <Text size="sm">{progress}%</Text>
                    </Group>
                    <Progress value={progress} animated={isProcessing} color={isProcessing ? 'blue' : 'green'} size="lg" />
                </Box>

                {/* Logs Section */}
                <Text size="xs" c="dimmed" mt="md">詳細ログ:</Text>
                <ScrollArea h="100%" type="auto" offsetScrollbars bg="dark.8" p="xs" style={{ borderRadius: '4px' }}>
                    <Stack gap={2}>
                        {logs.map((log, index) => (
                            <Text key={index} size="xs" ff="monospace" c="gray.3" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                                {log}
                            </Text>
                        ))}
                        {logs.length === 0 && <Text size="xs" c="dimmed">ログはありません</Text>}
                    </Stack>
                </ScrollArea>
            </Stack>
        </Drawer>
    );
}
