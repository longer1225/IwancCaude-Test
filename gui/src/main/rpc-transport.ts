// iwan-core daemon 的 TCP JSON-RPC 客户端（NDJSON 分帧）——Electron 主进程侧的"SocketClient"
//
// 【学习要点】本文件逐行为对齐 src/iwan_claude/core/transport/socket_client.py：
// 1) 请求带 id（uuid），响应靠 "jsonrpc" 字段识别并回填 pending 表；
// 2) 服务器主动推送包成 {"kind":"event","event":{...}}——无 id 无 jsonrpc 字段；
// 3) 单行最大 64MB（MCP 工具大结果），Node 的 readline 默认无限、够用，但仍显式设上限思想一致；
// 4) params 里【不放】type 字段（与 TUI 的 send_command 调用方式完全相同，服务端按 method 分派）。
import net from 'node:net'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { EventEmitter } from 'node:events'
import readline from 'node:readline'

import { DEFAULT_RETRY, retryDelayMs, shouldEnsureDaemon } from './retry'
import { findRepoRoot } from './daemon'

// 从 ~/.iwan/config.toml 文本里抠 [core] token（极简定向正则，不引 toml 解析依赖）
// 只在行首作用域内取 [core] 段第一次出现的 token = "..."
function parseCoreToken(text: string): string {
  const core = text.match(/^\[core\][\s\S]*?(?=^\[|$)/m)
  if (!core) return ''
  const kv = core[0].match(/^\s*token\s*=\s*"([^"]*)"/m)
  return kv ? kv[1] : ''
}

// 极简 .env 解析：KEY=VALUE，跳过注释与空行，去掉成对引号
// 【为什么不引 dotenv 依赖】只用来取几个地址/令牌，正则足够；取值语义与 daemon 侧的
// load_dotenv(override=False) 对齐：文件里的值只在进程环境没有该变量时才生效（见下面三级来源）
export function readProjectEnv(root: string): Record<string, string> {
  const out: Record<string, string> = {}
  let text = ''
  try {
    text = fs.readFileSync(path.join(root, '.env'), 'utf8')
  } catch {
    return out // 没有 .env 是常态，不是错误
  }
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq <= 0) continue
    const key = line
      .slice(0, eq)
      .trim()
      .replace(/^export\s+/, '')
    let value = line.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) out[key] = value
  }
  return out
}

// 仓库根 .env（进程内缓存一次：主进程启动后再改 .env，需要重启 GUI 才生效——与 daemon 同纪律）
let cachedProjectEnv: Record<string, string> | null = null
function projectEnv(): Record<string, string> {
  if (cachedProjectEnv === null) {
    cachedProjectEnv = readProjectEnv(findRepoRoot() ?? process.cwd())
  }
  return cachedProjectEnv
}

// daemon 地址的来源，用于日志/排查"我到底连了谁"
export type EndpointSource = 'env' | '.env' | 'default'

export interface DaemonEndpoint {
  host: string
  port: number
  source: EndpointSource
}

// 解析 daemon 地址：IWAN_* 环境变量 > 仓库根 .env > 内置默认（与 config.py 的优先级一致）
// 【为什么 GUI 必须读 .env】daemon 由本进程用 `uv run iwan-core`（cwd=仓库根）拉起，它读的
// 就是仓库根 .env；GUI 过去只看 process.env，于是用户按 README 把端口写进 .env 之后，
// GUI 仍去拨 7437 —— 连到的是"别人的 daemon"，自己 spawn 的那个反而永远连不上。
export function resolveDaemonEndpoint(): DaemonEndpoint {
  const fileEnv = projectEnv()
  const rawPort = process.env.IWAN_PORT ?? fileEnv.IWAN_PORT
  const rawHost = process.env.IWAN_HOST ?? fileEnv.IWAN_HOST
  const source: EndpointSource =
    process.env.IWAN_PORT || process.env.IWAN_HOST ? 'env' : rawPort || rawHost ? '.env' : 'default'
  const parsed = Number(rawPort ?? '7437')
  const port = Number.isFinite(parsed) && parsed > 0 ? parsed : 7437
  return { host: rawHost || '127.0.0.1', port, source }
}

export type RpcParams = Record<string, unknown>

interface Pending {
  resolve: (result: Record<string, unknown>) => void
  reject: (err: Error) => void
}

// 主进程 ⇄ 渲染进程转发的连接状态机
export type ConnStatus = 'connecting' | 'connected' | 'reconnecting' | 'error'

export class RpcTransport extends EventEmitter {
  private sock: net.Socket | null = null
  private rl: readline.Interface | null = null
  private pending = new Map<string, Pending>()
  private host = '127.0.0.1'
  private port = 7437
  // 鉴权令牌（协议缺口 #4）：空串 = 拨号后直接进入正常收发，不握手
  private token = ''
  private closedByUs = false
  status: ConnStatus = 'connecting'

  // daemon 地址的来源（env / .env / default）——排查"我到底连了谁的 daemon"用
  readonly endpointSource: EndpointSource

  // 从 IWAN_* 环境变量 > 仓库根 .env > 默认值 确定 daemon 地址（与 config.py 的优先级一致）
  constructor() {
    super()
    const endpoint = resolveDaemonEndpoint()
    this.host = endpoint.host
    this.port = endpoint.port
    this.endpointSource = endpoint.source
    // 连接目标必须可见：否则"连到别人的 daemon"是完全静默的（改代码不生效、极难排查）
    console.log(`[rpc] daemon 目标 ${endpoint.host}:${endpoint.port}（来源：${endpoint.source}）`)
    // 令牌三级来源：环境变量 > 项目 .env > ~/.iwan/config.toml [core] token > 空(免鉴权)
    this.token = process.env.IWAN_TOKEN ?? projectEnv().IWAN_TOKEN ?? ''
    if (!this.token) {
      try {
        this.token = parseCoreToken(
          fs.readFileSync(path.join(os.homedir(), '.iwan', 'config.toml'), 'utf8')
        )
      } catch {
        this.token = '' // 配置文件不存在 = 无令牌，与 daemon 端"缺省静默跳过"同纪律
      }
    }
  }

  // 设置"连不上就拉起 daemon"的重试策略挂钩：快档 → 低频退避，**不会最终放弃**
  // （详细节奏见 retry.ts；旧实现 120 次后进终态，daemon 晚到就永远连不上）
  async start(ensureDaemon: () => Promise<void>): Promise<void> {
    this.closedByUs = false
    let attempt = 0
    let exhausted = false
    const tryOnce = async (): Promise<void> => {
      if (this.closedByUs) return
      try {
        await this.dial()
        return
      } catch {
        /* 本次失败：落到下面的节奏控制 */
      }
      attempt += 1
      if (this.closedByUs) return
      // 懒启动：首次失败调一次；低频阶段每 ensureEvery 次再试（daemon 被杀了要有人拉起）
      if (shouldEnsureDaemon(attempt)) await ensureDaemon().catch(() => undefined)
      if (attempt <= DEFAULT_RETRY.fastAttempts) {
        this.setStatus(attempt === 1 ? 'connecting' : 'reconnecting')
      } else if (!exhausted) {
        // 快档用尽：置 error（界面显示失败原因），但**继续**低频重试——
        // daemon 晚到或用户修好配置后，下一轮就能自愈，不需要重启窗口
        exhausted = true
        this.setStatus('error')
      }
      setTimeout(() => {
        void tryOnce()
      }, retryDelayMs(attempt))
    }
    void tryOnce()
  }

  // 建立 TCP 连接并挂上行读取/派发逻辑；error 监听只在"握手未完成"阶段负责
  // reject 本次 dial，连上之后立刻摘除，换 readLoop 的常驻兜底
  private dial(): Promise<void> {
    return new Promise((resolve, reject) => {
      const sock = net.createConnection({ host: this.host, port: this.port })
      let settled = false
      sock.once('connect', () => {
        settled = true
        sock.removeListener('error', onErr)
        this.sock = sock
        this.readLoop(sock)
        // 有令牌：readLoop 已就位（hello 应答走 dispatch 回填 pending），
        // 握手成功才算 connected；失败 destroy 后 reject，交给外层重试环兜底
        if (!this.token) {
          this.setStatus('connected')
          resolve()
          return
        }
        this.request('auth.hello', { token: this.token })
          .then(() => {
            this.setStatus('connected')
            resolve()
          })
          .catch((err: Error) => {
            this.sock = null
            sock.destroy()
            reject(err)
          })
      })
      const onErr = (err: Error): void => {
        sock.destroy()
        if (!settled) reject(err)
      }
      sock.once('error', onErr)
    })
  }

  // readline 按行分帧 NDJSON；断线后清空 pending（渲染层收到 reconnecting 状态自行重订阅）
  private readLoop(sock: net.Socket): void {
    // 【学习要点】error 兜底要挂【三个对象】，少一个就是一场冻结事故：
    // taskkill 杀 daemon 以 RST 收尾时——①socket 层的 error 先由 no-op 吸收
    // （node 对无监听者的流 error 直接 throw，沿 libuv 冒成未捕获异常，
    // Electron 主进程默认弹原生错误对话框并阻塞整个主线程）；②readline 会把
    // input 流的错误【代理再发一遍到它自己的 Interface 实例】（proxyEvents
    // 机制），rl 无监听照样炸第二发；③最关键：错误被吸收后 readline 的
    // 'close' 在 RST 路径上根本不来（实测），只挂 rl.on('close') 重连会永远
    // 不触发——GUI 卡死 reconnecting 假活。重连触发点必须挂在 socket 的
    // 'close' 上（EOF/RST 都必达），与 rl.close 用 done 标志去重。
    sock.on('error', () => {})
    const rl = readline.createInterface({ input: sock })
    rl.on('error', () => {})
    this.rl = rl
    rl.on('line', (line) => this.dispatch(line))
    let done = false
    const onGone = (): void => {
      if (done) return
      done = true
      const hadPending = this.pending.size > 0
      for (const p of this.pending.values()) p.reject(new Error('connection lost'))
      this.pending.clear()
      if (!this.closedByUs) {
        this.setStatus('reconnecting')
        // 指数退避重连：1s 起步封顶 10s
        const backoff = (ms: number): void => {
          setTimeout(() => {
            this.dial().catch(() => {
              if (!this.closedByUs) backoff(Math.min(ms * 2, 10000))
            })
          }, ms)
        }
        backoff(hadPending ? 500 : 1000)
      }
    }
    rl.on('close', onGone)
    sock.on('close', onGone)
  }

  // 单行消息派发：有 jsonrpc → 回填 pending；kind=event → 发 'event' 给上层
  private dispatch(line: string): void {
    if (!line.trim()) return
    let msg: Record<string, unknown>
    try {
      msg = JSON.parse(line) as Record<string, unknown>
    } catch {
      return // 容错：坏行直接丢弃（同 Python 端 _dispatch 的 JSONDecodeError 分支）
    }
    if ('jsonrpc' in msg) {
      const id = msg.id as string | undefined
      const p = id ? this.pending.get(id) : undefined
      if (p && id) {
        this.pending.delete(id)
        if (msg.error) {
          const err = msg.error as { code?: number; message?: string }
          p.reject(new Error(`[${err.code ?? -1}] ${err.message ?? 'unknown'}`))
        } else {
          p.resolve((msg.result ?? {}) as Record<string, unknown>)
        }
      }
    } else if (msg.kind === 'event') {
      this.emit('event', msg.event as Record<string, unknown>)
    }
  }

  // 发送 JSON-RPC 请求返回 result——信封格式与 envelope.JsonRpcRequest 的 model_dump 一致
  request(method: string, params: RpcParams): Promise<Record<string, unknown>> {
    if (!this.sock || this.sock.destroyed) return Promise.reject(new Error('daemon 未连接'))
    const id = randomUUID()
    const req = { jsonrpc: '2.0', id, method, params }
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.sock!.write(JSON.stringify(req) + '\n', (err) => {
        if (err) {
          this.pending.delete(id)
          reject(err)
        }
      })
    })
  }

  // 主动关闭（app quit 时）：不再触发重连
  stop(): void {
    this.closedByUs = true
    this.rl?.close()
    this.sock?.destroy()
    this.sock = null
  }

  private setStatus(s: ConnStatus): void {
    this.status = s
    this.emit('status', s)
  }
}
