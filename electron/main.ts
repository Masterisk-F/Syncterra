import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import * as child_process from 'child_process';
import * as net from 'net';

// app.isPackaged: true=本番ビルド, false=開発モード
const isDev = !app.isPackaged;

let mainWindow: BrowserWindow | null = null;
let pythonProcess: child_process.ChildProcess | null = null;
let backendPort: number = 0;

/**
 * 空きポートを見つける
 */
function findAvailablePort(): Promise<number> {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.listen(0, '127.0.0.1', () => {
            const address = server.address();
            if (address && typeof address === 'object') {
                const port = address.port;
                server.close(() => resolve(port));
            } else {
                reject(new Error('Failed to get port'));
            }
        });
        server.on('error', reject);
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true,
        },
    });

    // 開発モード: ViteのHMRを利用、本番: resourcesにバンドルされたファイル
    const startUrl = isDev
        ? 'http://localhost:5173'
        : `file://${path.join(process.resourcesPath, 'renderer', 'index.html')}`;

    mainWindow.loadURL(startUrl);

    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => (mainWindow = null));
}

async function startPythonBackend() {
    // 空きポートを見つける（開発/本番共通）
    backendPort = await findAvailablePort();
    console.log('Starting Python backend on port:', backendPort);

    const runCommand = isDev ? 'uv' : path.join(process.resourcesPath, 'backend');
    const args = isDev
        ? ['run', '-m', 'backend.main', '--port', String(backendPort)]
        : ['--port', String(backendPort)];

    const cwd = isDev ? path.join(__dirname, '..', '..') : path.dirname(runCommand);

    // DB保存場所: 本番のみ userData を使用、開発は ./db
    const dbDir = isDev
        ? path.join(__dirname, '..', '..', 'db')
        : path.join(app.getPath('userData'), 'db');
    console.log('Database Directory:', dbDir);

    pythonProcess = child_process.spawn(runCommand, args, {
        cwd: cwd,
        stdio: 'inherit',
        env: { ...process.env, SYNCTERRA_DB_DIR: dbDir }
    });

    pythonProcess.on('error', (err) => {
        console.error('Failed to start Python backend:', err);
    });

    pythonProcess.on('exit', (code, signal) => {
        console.log(`Python backend exited with code ${code} and signal ${signal}`);
        pythonProcess = null;
    });
}

// IPC: フロントエンドにバックエンドのポート番号を返す
ipcMain.handle('get-backend-port', () => {
    return backendPort;
});

app.on('ready', async () => {
    // 開発/本番共通でバックエンドを起動
    await startPythonBackend();
    // バックエンドの起動を少し待つ
    await new Promise(resolve => setTimeout(resolve, 1500));
    createWindow();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('will-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});
