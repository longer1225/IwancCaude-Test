// preload 注入的 window.iwan 桥的类型声明——渲染层全局唯一的外联面
interface IwanBridge {
  request(method: string, params?: Record<string, unknown>): Promise<{ ok: boolean; result?: Record<string, unknown>; error?: string }>
  onEvent(cb: (event: Record<string, unknown>) => void): () => void
  onStatus(cb: (status: string) => void): () => void
  pickDirectory(): Promise<string | null>
  getStatus(): Promise<string>
  getStatusDetail(): Promise<string>
  onStatusDetail(cb: (detail: string) => void): () => void
  getDaemonIdentity(): Promise<IwanDaemonIdentity>
  onDaemonIdentity(cb: (info: IwanDaemonIdentity) => void): () => void
  readDir(root: string, rel: string): Promise<Array<{ name: string; dir: boolean }>>
  readFile(root: string, rel: string): Promise<{ text: string; truncated: boolean; size: number; binary: boolean }>
  sessionsMeta(ids: string[]): Promise<Record<string, { cwd: string; created_at: string; run_ids: string[] }>>
  runTasks(sid: string, runId: string): Promise<Array<Record<string, unknown>>>
  readConfig(): Promise<{ exists: boolean; raw: string; toml: unknown }>
  readRagEval(): Promise<{ exists: boolean; data: unknown }>
  // 本机密钥文件（~/.iwan/secrets.env）：只给名字+尾号，明文不出主进程
  listSecrets(): Promise<Array<{ name: string; hint: string }>>
  setSecret(name: string, value: string): Promise<{ name: string; hint: string }>
  deleteSecret(name: string): Promise<void>
  // 手动触发一次 daemon 拉起（存好 key 后立刻重试，不等低频重连节奏）
  retryDaemon(): Promise<boolean>
  getSettings(): Promise<Record<string, unknown>>
  setSettings(patch: Record<string, unknown>): Promise<Record<string, unknown>>
  openPath(p: string): Promise<string>
  pickFile(): Promise<string | null>
  // 自绘顶栏窗口控制：新窗口/最小化/最大化切换/关闭 + 最大化态订阅（初值靠 winIsMaximized 补查）
  newWindow(): void
  winMinimize(): void
  winToggleMaximize(): void
  winClose(): void
  winIsMaximized(): Promise<boolean>
  onWinMaximized(cb: (maximized: boolean) => void): () => void
}

declare global {
  // 【为什么放在 declare global 里】本文件末尾有 `export {}`，属于模块作用域；
  // 只有 declare global 内的声明才是全局可见的类型（store.ts / TitleBar 直接用得到）
  interface IwanDaemonIdentity {
    external: boolean
    daemonRoot: string
    localRoot: string
    message: string
  }
  interface Window {
    iwan: IwanBridge
  }
}

export {}
