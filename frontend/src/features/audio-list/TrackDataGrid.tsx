import { useMemo, useCallback } from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef, ValueFormatterParams, GridReadyEvent, ICellRendererParams, CellStyle, CellKeyDownEvent } from 'ag-grid-community';
import { useMantineColorScheme } from '@mantine/core';
import { themeQuartz, colorSchemeDarkBlue } from 'ag-grid-community';
import type { Track } from '../../api/types';

interface TrackDataGridProps {
    tracks: Track[];
    onGridReady: (params: GridReadyEvent) => void;
    onSyncToggle?: (id: number, val: boolean) => void;
    readOnlySync?: boolean;
    showSyncColumn?: boolean;
    showSelectionCheckbox?: boolean;
}

// ファイルサイズをMB表示にフォーマット
const formatFileSize = (bytes: number | null): string => {
    if (bytes === null || bytes === undefined) return '';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

// 再生時間を分:秒表示にフォーマット
const formatDuration = (seconds: number | null): string => {
    if (seconds === null || seconds === undefined) return '';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
};

// 日時フォーマット (YYYY-MM-DD HH:mm:ss)
const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        return date.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
    } catch {
        return dateStr;
    }
};

export default function TrackDataGrid({
    tracks,
    onGridReady,
    onSyncToggle,
    readOnlySync = false,
    showSyncColumn = true,
    showSelectionCheckbox = true,
}: TrackDataGridProps) {
    const { colorScheme } = useMantineColorScheme();

    const gridTheme = useMemo(() => {
        return colorScheme === 'dark'
            ? themeQuartz.withPart(colorSchemeDarkBlue)
            : themeQuartz;
    }, [colorScheme]);

    // Space Key Handler for Sync Toggle
    const onCellKeyDown = useCallback((event: CellKeyDownEvent) => {
        if (readOnlySync || !onSyncToggle) return;

        if (event.event instanceof KeyboardEvent && (event.event.code === 'Space' || event.event.code === 'Enter')) {
            const colId = event.column.getColId();
            if (colId === 'sync' && event.data) {
                // Prevent default scrolling behavior
                event.event.preventDefault();
                onSyncToggle(event.data.id, event.data.sync);
            }
        }
    }, [readOnlySync, onSyncToggle]);

    const columnDefs = useMemo<ColDef<Track>[]>(() => {
        const cols: ColDef<Track>[] = [
            {
                field: 'msg',
                headerName: '!',
                width: 50,
                cellStyle: { textAlign: 'center' } as CellStyle,
                checkboxSelection: showSelectionCheckbox,
                headerCheckboxSelection: showSelectionCheckbox,
            },
        ];

        if (showSyncColumn) {
            cols.push({
                field: 'sync',
                headerName: '同期',
                width: 70,
                editable: false,
                cellRenderer: (params: ICellRendererParams) => {
                    return (
                        <div
                            style={{
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                height: '100%',
                                width: '100%',
                                cursor: readOnlySync ? 'default' : 'pointer'
                            }}
                            onClick={() => {
                                if (!readOnlySync && onSyncToggle) {
                                    onSyncToggle(params.data.id, params.value);
                                }
                            }}
                        >
                            <input
                                type="checkbox"
                                checked={params.value}
                                readOnly
                                disabled={readOnlySync}
                                style={{
                                    cursor: readOnlySync ? 'default' : 'pointer',
                                    margin: 0
                                }}
                            />
                        </div>
                    );
                },
                cellStyle: { display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 0 } as CellStyle,
            });
        }

        cols.push(
            {
                field: 'title',
                headerName: 'タイトル',
                width: 200,
                filter: true,
                sortable: true,
            },
            {
                field: 'artist',
                headerName: 'アーティスト',
                width: 150,
                filter: true,
                sortable: true,
            },
            {
                field: 'album_artist',
                headerName: 'アルバムアーティスト',
                width: 150,
                filter: true,
                sortable: true,
            },
            {
                field: 'composer',
                headerName: '作曲者',
                width: 150,
                filter: true,
                sortable: true,
            },
            {
                field: 'album',
                headerName: 'アルバム',
                width: 200,
                filter: true,
                sortable: true,
            },
            {
                field: 'track_num',
                headerName: '#',
                width: 80,
                cellStyle: { textAlign: 'center' } as CellStyle,
            },
            {
                field: 'duration',
                headerName: '長さ',
                width: 90,
                valueFormatter: (params: ValueFormatterParams) => formatDuration(params.value),
                cellStyle: { textAlign: 'right' } as CellStyle,
            },
            {
                field: 'file_name',
                headerName: 'ファイル名',
                width: 200,
                filter: true,
            },
            {
                field: 'file_path',
                headerName: 'ファイルパス',
                width: 300,
                filter: true,
            },
            {
                field: 'relative_path',
                headerName: '同期先相対パス',
                width: 250,
            },
            {
                field: 'codec',
                headerName: 'コーデック',
                width: 100,
                filter: true,
            },
            {
                field: 'size',
                headerName: 'サイズ',
                width: 110,
                valueFormatter: (params: ValueFormatterParams) => formatFileSize(params.value),
                cellStyle: { textAlign: 'right' } as CellStyle,
            },
            {
                field: 'added_date',
                headerName: '追加日時',
                width: 170,
                sortable: true,
                valueFormatter: (params: ValueFormatterParams) => formatDate(params.value),
            },
            {
                field: 'last_modified',
                headerName: '更新日時',
                width: 170,
                sortable: true,
                valueFormatter: (params: ValueFormatterParams) => formatDate(params.value),
            },
        );

        return cols;
    }, [showSyncColumn, readOnlySync, onSyncToggle, showSelectionCheckbox]);

    const defaultColDef = useMemo<ColDef>(() => ({
        resizable: true,
        sortable: false,
        filter: false,
    }), []);

    return (
        <AgGridReact<Track>
            onGridReady={onGridReady}
            rowData={tracks}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            rowSelection="multiple"
            enableRangeSelection={false}
            enableCellTextSelection={true}
            suppressMenuHide={true}
            animateRows={true}
            theme={gridTheme}
            onCellKeyDown={onCellKeyDown}
            getRowId={(params) => String(params.data.id)}
        />
    );
}
