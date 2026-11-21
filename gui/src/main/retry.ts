// 重连节奏：先"快档"（冷启动窗口），再用完转低频退避——**永不放弃**。
//
// 【为什么不能有"最终失败"】daemon 冷启动要几十秒；GUI 常常先起来、daemon 后起来
// （或者用户先把 key 修好、再启动 daemon）。旧实现 120 次 ×1s 后直接进入终态，
// 之后即使 daemon 就在 7437 上听着，窗口也永远显示"连接失败"，只能重启窗口。
//
// 【节奏】快档 120 次 ×1s（覆盖冷启动）→ 低频 5s、10s、20s、30s 封顶，之后一直 30s。
// 低频阶段仍会周期性调用 ensureDaemon（否则 daemon 被杀后没人再拉起它）。
export interface RetryPolicy {
  fastAttempts: number // 快档尝试次数
  fastDelayMs: number // 快档间隔
  baseMs: number // 低频退避起点
  maxMs: number // 低频退避上限
  ensureEvery: number // 低频阶段每 N 次尝试懒启动一次 daemon
}

// 环境变量只为测试/排障留口子：默认值就是产品行为
function envInt(name: string, fallback: number): number {
  const n = Number(process.env[name] ?? '')
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback
}

export const DEFAULT_RETRY: RetryPolicy = {
  fastAttempts: envInt('IWAN_GUI_FAST_ATTEMPTS', 120),
  fastDelayMs: 1000,
  baseMs: envInt('IWAN_GUI_RETRY_BASE_MS', 5000),
  maxMs: envInt('IWAN_GUI_RETRY_MAX_MS', 30000),
  ensureEvery: envInt('IWAN_GUI_ENSURE_EVERY', 5),
}

// 第 attempt 次失败后的等待毫秒数（attempt 从 1 开始）
// 快档内固定 fastDelayMs；之后按 baseMs 翻倍，翻到 maxMs 后保持（k 先夹到 6，避免溢出）
export function retryDelayMs(attempt: number, p: RetryPolicy = DEFAULT_RETRY): number {
  if (attempt <= p.fastAttempts) return p.fastDelayMs
  const k = Math.min(Math.max(attempt - p.fastAttempts - 1, 0), 6)
  return Math.min(p.baseMs * 2 ** k, p.maxMs)
}

// 低频阶段是否该顺手拉起 daemon（冷启动 1 次 + 之后每 ensureEvery 次）
export function shouldEnsureDaemon(attempt: number, p: RetryPolicy = DEFAULT_RETRY): boolean {
  if (attempt <= 0) return false
  if (attempt > p.fastAttempts) return attempt % p.ensureEvery === 0
  return attempt === 1
}
