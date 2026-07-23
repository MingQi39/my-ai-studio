import { app, BrowserWindow, ipcMain, nativeImage, shell } from 'electron/main';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  pushInterviewNow,
  requestDesktopPushPermission,
  startInterviewPushScheduler,
  stopInterviewPushScheduler,
} from './push-scheduler';
import type { InterviewPushSchedulerConfig } from './push-types';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

process.env.DIST = path.join(__dirname, '../build');
process.env.VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL;

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;

function resolveAppIconPath() {
  const candidates = [
    path.join(__dirname, '../electron/icon.png'),
    path.join(app.getAppPath(), 'electron/icon.png'),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function createWindow() {
  const iconPath = resolveAppIconPath();
  const icon = iconPath ? nativeImage.createFromPath(iconPath) : undefined;
  if (icon && process.platform === 'darwin') {
    app.dock?.setIcon(icon);
  }

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: 'Qi AI Studio',
    icon,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    void mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: 'right' });
  } else {
    void mainWindow.loadFile(path.join(process.env.DIST!, 'index.html'));
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: 'deny' };
  });
}

function focusInterviewRoute() {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  void mainWindow.webContents.executeJavaScript(
    `window.location.hash = '#/interview?openLearn=1'`,
    true,
  );
}

app.whenReady().then(() => {
  createWindow();

  ipcMain.handle('push:request-permission', () => requestDesktopPushPermission());
  ipcMain.handle('push:sync-scheduler', (_event, config: InterviewPushSchedulerConfig) => {
    startInterviewPushScheduler(config, focusInterviewRoute);
  });
  ipcMain.handle('push:stop-scheduler', () => {
    stopInterviewPushScheduler();
  });
  ipcMain.handle('push:push-now', (_event, config?: InterviewPushSchedulerConfig | null) => {
    return pushInterviewNow(config);
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  stopInterviewPushScheduler();
  if (process.platform !== 'darwin') app.quit();
});
