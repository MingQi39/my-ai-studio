import { platform as webPlatform } from './web';
import { platform as electronPlatform } from './electron';
import type { Platform } from './types';

export function isElectronRuntime(): boolean {
  return typeof window !== 'undefined' && Boolean(window.electronAPI?.isDesktop);
}

export function getPlatform(): Platform {
  return isElectronRuntime() ? electronPlatform : webPlatform;
}

export { webPlatform };
