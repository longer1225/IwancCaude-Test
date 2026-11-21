// 设置页：外观 | 项目 | MCP | 审批与信任 | 模型与 API | 引擎 | 检索质量 | 关于
//
// 【学习要点】这里演示了混合数据源的诚实分层——同一张界面里三种"写权限"：
// ① 外观/项目：GUI 自己的 ~/.iwan/gui.json，随便改；
// ② 信任表：daemon 的 trust.list/revoke，真命令真写；
// ③ 模型与 API：GUI 唯一能改 daemon 配置的分区——但它不自己写 config.toml，
//    而是走 llm.config.set 让 daemon 校验+落盘+立即生效（写后端配置=改行为合同，
//    必须由后端自己收口）；daemon 连不上时只剩 secrets.env 这一条离线自救通道。
import { useEffect, useState } from 'react'
import { rpc } from '../rpc'
import { useGui } from '../guiHelpers'
import { useStore, refreshLlmConfig, saveLlmConfig, testLlmConfig } from '../store'
import type { LlmConfigResult, PongResult, TrustListResult } from '../protocol/types'
import { Icon } from './Icon'
import type { IconName } from './Icon'
import { baseName } from '../guiHelpers'

type Section = 'appearance' | 'projects' | 'mcp' | 'trust' | 'model' | 'engine' | 'quality' | 'about'

const SECTIONS: Array<[Section, string, IconName]> = [
  ['appearance', '外观', 'sun'],
  ['projects', '项目', 'folder'],
  ['mcp', 'MCP 服务', 'plug'],
  ['trust', '审批与信任', 'shield'],
  ['model', '模型与 API', 'sparkle'],
  ['engine', '引擎', 'cpu'],
  ['quality', '检索质量', 'search'],
  ['about', '关于', 'message']
]

// 外观区：主题三选 + 字号步进
function AppearanceSection() {
  const gui = useGui()
  return (
    <>
      <div className="set-row">
        <span className="set-label">主题</span>
        <div className="seg">
          {(['light', 'dark', 'system'] as const).map((t) => (
            <button key={t} className={gui.theme === t ? 'on' : ''} onClick={() => gui.set({ theme: t })}>
              {t === 'light' ? '浅色' : t === 'dark' ? '深色' : '跟随系统'}
            </button>
          ))}
        </div>
      </div>
      <div className="set-row">
        <span className="set-label">界面字号</span>
        <Stepper value={gui.uiFontPx} onChange={(v) => gui.set({ uiFontPx: v })} />
      </div>
      <div className="set-row">
        <span className="set-label">代码字号</span>
        <Stepper value={gui.codeFontPx} onChange={(v) => gui.set({ codeFontPx: v })} />
      </div>
      <div className="set-row">
        <span className="set-label">整体缩放</span>
        <div className="seg">
          {[0.9, 1, 1.1, 1.25].map((f) => (
            <button key={f} className={gui.fontScale === f ? 'on' : ''} onClick={() => gui.set({ fontScale: f })}>
              {Math.round(f * 100)}%
            </button>
          ))}
        </div>
      </div>
      <p className="set-note">设置写入 ~/.iwan/gui.json——daemon 对这份文件一无所知（用户设置与服务数据分轨，VS Code 同款纪律）。</p>
    </>
  )
}

// 字号步进器（8~24px 限幅）
function Stepper(props: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="stepper">
      <button onClick={() => props.onChange(Math.max(10, Math.round((props.value - 0.5) * 10) / 10))}>−</button>
      <span>{props.value}px</span>
      <button onClick={() => props.onChange(Math.min(24, Math.round((props.value + 0.5) * 10) / 10))}>＋</button>
    </div>
  )
}

// 项目区：登记表管理（添加/打开/移除）
function ProjectsSection() {
  const gui = useGui()
  const add = async (): Promise<void> => {
    const dir = await window.iwan.pickDirectory()
    if (dir) gui.addProject(dir)
  }
  return (
    <>
      <p className="set-note">登记的项目会固定显示在侧栏分组里（哪怕暂时没有会话）。</p>
      {gui.projects.length === 0 && <div className="pane-hint">还没有登记项目。</div>}
      {gui.projects.map((p) => (
        <div key={p} className="set-row row-line" title={p}>
          <Icon name="folder" size={14} />
          <span className="set-label grow">{baseName(p)}</span>
          <button className="mini-btn" onClick={() => void window.iwan.openPath(p)}><Icon name="folderOpen" size={12} /></button>
          <button className="mini-btn danger" onClick={() => gui.removeProject(p)}><Icon name="trash" size={12} /></button>
        </div>
      ))}
      <button className="mini-btn" style={{ marginTop: 10 }} onClick={() => void add()}>
        <Icon name="folderPlus" size={12} /> 添加项目
      </button>
    </>
  )
}

// MCP 区：config.toml 的 [[mcp.servers]] 只读卡片
interface McpServer { name: string; transport: string; command?: string; host?: string; port?: string; timeout_sec?: string }
function McpSection() {
  const [cfg, setCfg] = useState<{ exists: boolean; raw: string; toml: unknown } | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  useEffect(() => {
    void window.iwan.readConfig().then(setCfg).catch(() => setCfg({ exists: false, raw: '', toml: null }))
  }, [])
  const servers: McpServer[] = ((cfg?.toml as { arrays?: Record<string, Array<Record<string, string>>> } | null)?.arrays?.['mcp.servers'] ?? []).map((s) => ({
    name: s.name ?? '(未命名)',
    transport: s.transport ?? (s.command ? 'stdio' : s.host ? 'tcp' : '?'),
    command: s.command ? `${s.command} ${s.args ?? ''}`.trim() : undefined,
    host: s.host,
    port: s.port,
    timeout_sec: s.timeout_sec
  }))
  return (
    <>
      <p className="set-note">
        MCP（Model Context Protocol）让 daemon 挂载外部工具服务器，工具以
        <code>mcp__服务器名__工具名</code> 注册进模型的可调用清单。此面板为<b>只读</b>：
        配置在 <code>~/.iwan/config.toml</code> 的 <code>[[mcp.servers]]</code> 段，改完重启 iwan-core 生效。
      </p>
      {!cfg && <div className="pane-hint">读取 config.toml…</div>}
      {cfg && !cfg.exists && <div className="pane-hint">~/.iwan/config.toml 不存在——当前没有任何 MCP 服务器。</div>}
      {cfg?.exists && servers.length === 0 && <div className="pane-hint">config.toml 里没有 [[mcp.servers]] 条目。</div>}
      {servers.map((s) => (
        <div key={s.name} className="mcp-card">
          <div className="mcp-head">
            <Icon name="plug" size={14} />
            <span className="mcp-name">{s.name}</span>
            <span className="mcp-tag">{s.transport}</span>
            <span className="grow" />
            <span className="dot dot-connected" title="已配置（在线状态随 daemon）" />
          </div>
          <div className="mcp-body">
            {s.command && <div><code>{s.command}</code></div>}
            {s.host && <div>{s.host}:{s.port ?? '?'} · timeout {s.timeout_sec ?? '30'}s</div>}
          </div>
        </div>
      ))}
      {cfg?.exists && (
        <>
          <button className="mini-btn" style={{ marginTop: 8 }} onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? '收起原文' : '查看 config.toml 原文'}
          </button>
          {showRaw && <pre className="toml-raw">{cfg.raw}</pre>}
        </>
      )}
    </>
  )
}

// 审批与信任区：规则序讲解 + trust.list 表 + revoke
function TrustSection() {
  const [entries, setEntries] = useState<Record<string, string> | null>(null)
  const [err, setErr] = useState('')
  const refresh = (): void => {
    rpc<TrustListResult>('trust.list')
      .then((r) => setEntries(r.entries ?? {}))
      .catch((e) => {
        setEntries({})
        setErr(String(e instanceof Error ? e.message : e))
      })
  }
  useEffect(refresh, [])
  const revoke = (cwd: string): void => {
    void rpc('trust.revoke', { cwd }).then(refresh).catch((e) => setErr(String(e)))
  }
  return (
    <>
      <p className="set-note">
        权限判定序：<b>deny → ask → allow，先匹配先赢</b>；未命中任何规则的动作默认弹询问（default-ask）。
        审批模式是会话级开关（输入框左下），而下表是<b>目录级信任</b>——daemon 记住你对某项目目录的放行决定。
      </p>
      {err && <div className="pane-note">{err}</div>}
      {entries === null && <div className="pane-hint">读取信任表…</div>}
      {entries && Object.keys(entries).length === 0 && <div className="pane-hint">信任表为空——首次进入未信任目录时会在会话里弹出询问卡。</div>}
      {Object.entries(entries ?? {}).map(([cwd, decision]) => (
        <div key={cwd} className="set-row row-line" title={cwd}>
          <Icon name="shield" size={14} />
          <span className="set-label grow">{baseName(cwd) || cwd}</span>
          <span className={`chg-badge${decision === 'allow' ? ' chg-add' : ''}`}>{decision}</span>
          <button className="mini-btn danger" onClick={() => revoke(cwd)} title="撤销该目录的信任决定">撤销</button>
        </div>
      ))}
      <p className="set-note">★ 权限规则（allow/deny 清单）的 GUI 编辑尚未开放——后端规则引擎在 settings 层，接入需协议补全，另行立项。</p>
    </>
  )
}

// ==================== 模型与 API ====================
// 【设计】这一区是 GUI 里唯一能改 daemon 配置的地方，所以把"改了之后谁说了算"
// 摆在最上面：daemon 在线 → llm.config.set（校验+落盘+立即生效）；daemon 离线 →
// 只有本机 secrets.env 一条通道（缺 key 时 daemon 起不来，用户没有别的自救路）。
interface LlmForm {
  provider: string
  baseUrl: string
  apiKeyEnv: string
  defaultModel: string
  contextWindow: string
  fast: string
  balanced: string
  powerful: string
}

const PROVIDERS: Array<[string, string]> = [
  ['anthropic', 'Anthropic 兼容'],
  ['openai_compatible', 'OpenAI 兼容']
]

// 常见模型名：只做输入提示（datalist），不限制用户填任意名字
const MODEL_SUGGESTIONS = [
  'deepseek-chat',
  'deepseek-reasoner',
  'claude-sonnet-4-6',
  'claude-opus-4-1-20250805',
  'gpt-4o',
  'qwen-max',
  'glm-4-plus'
]

// 端点快捷填充：换服务商时最容易写错的就是 base_url 的形态，以及"该配哪种协议"
const BASE_URL_PRESETS: Array<[string, string, string]> = [
  ['DeepSeek', 'https://api.deepseek.com/anthropic', 'anthropic'],
  ['DeepSeek·OpenAI', 'https://api.deepseek.com/v1', 'openai_compatible'],
  ['通义千问', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'openai_compatible'],
  ['本地 Ollama', 'http://127.0.0.1:11434/v1', 'openai_compatible']
]

// 快照 → 表单草稿：覆盖过的档位才预填，未覆盖的留空并用占位符显示内置值
function toForm(cfg: LlmConfigResult): LlmForm {
  const over = new Set(cfg.preset_overrides)
  return {
    provider: cfg.provider,
    baseUrl: cfg.base_url,
    apiKeyEnv: cfg.api_key_env,
    defaultModel: cfg.default_model,
    contextWindow: String(cfg.context_window),
    fast: over.has('fast') ? cfg.presets.fast ?? '' : '',
    balanced: over.has('balanced') ? cfg.presets.balanced ?? '' : '',
    powerful: over.has('powerful') ? cfg.presets.powerful ?? '' : ''
  }
}

// 密钥来源的人话（GUI 最容易被误解的一行：磁盘上有值 ≠ 这次跑的就是它）
function keySourceLabel(cfg: LlmConfigResult): string {
  if (!cfg.api_key_set) return '未配置'
  if (cfg.api_key_source === 'secrets') return `本机保存${cfg.api_key_hint}`
  if (cfg.api_key_source === 'env') return `环境变量 ${cfg.api_key_env}${cfg.api_key_hint}`
  return `已配置${cfg.api_key_hint}`
}

function ModelSection() {
  const status = useStore((s) => s.status)
  const cfg = useStore((s) => s.llmConfig)
  const [form, setForm] = useState<LlmForm | null>(null)
  const [keyDraft, setKeyDraft] = useState('')
  const [offlineName, setOfflineName] = useState('DEEPSEEK_API_KEY')
  const [offlineKey, setOfflineKey] = useState('')
  const [secrets, setSecrets] = useState<Array<{ name: string; hint: string }>>([])
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState<{
    kind: 'ok' | 'warn' | 'err'
    text: string
    items?: string[]
  } | null>(null)
  const connected = status === 'connected'

  // 进面板拉一次快照（daemon 在线才有；离线时界面只剩本机密钥那一条通道）
  useEffect(() => {
    void refreshLlmConfig()
  }, [])
  // 快照到达后填表单；已经填过就不覆盖用户正在改的草稿
  useEffect(() => {
    if (cfg) setForm((prev) => prev ?? toForm(cfg))
  }, [cfg])
  // 本机密钥表：连上也展示（用户要能确认"key 到底存在哪一层"）
  const reloadSecrets = (): void => {
    void window.iwan
      .listSecrets()
      .then(setSecrets)
      .catch(() => setSecrets([]))
  }
  useEffect(reloadSecrets, [connected])

  const patch = (p: Partial<LlmForm>): void => setForm((prev) => (prev ? { ...prev, ...p } : prev))

  // 保存整份模型配置：daemon 校验 → 写 config.toml + secrets.env → 立即生效
  const save = async (): Promise<void> => {
    if (!form) return
    setBusy('save')
    setNotice(null)
    try {
      const r = await saveLlmConfig({
        provider: form.provider,
        base_url: form.baseUrl.trim(),
        api_key_env: form.apiKeyEnv.trim(),
        default_model: form.defaultModel.trim(),
        context_window: Number(form.contextWindow) || 128000,
        presets: {
          fast: form.fast.trim(),
          balanced: form.balanced.trim(),
          powerful: form.powerful.trim()
        },
        ...(keyDraft.trim() ? { api_key: keyDraft.trim() } : {})
      })
      setForm(toForm(r))
      setKeyDraft('')
      reloadSecrets()
      const warns = r.warnings ?? []
      setNotice(
        warns.length
          ? { kind: 'warn', text: '已保存并生效，但有环境变量会在重启后盖回：', items: warns }
          : { kind: 'ok', text: '已保存并生效——下一次运行起使用新的模型/端点' }
      )
    } catch (e) {
      setNotice({ kind: 'err', text: `保存失败：${String(e instanceof Error ? e.message : e)}` })
    } finally {
      setBusy('')
    }
  }

  // 用当前配置真打一次 API：把 401/404/模型不存在这类真实原因显示出来
  const test = async (): Promise<void> => {
    setBusy('test')
    setNotice(null)
    try {
      const r = await testLlmConfig()
      setNotice(
        r.ok
          ? { kind: 'ok', text: `连通正常：${r.model}（${r.latency_ms} ms）` }
          : { kind: 'err', text: `连接失败 · ${r.model}（${r.latency_ms} ms）：${r.error}` }
      )
    } catch (e) {
      setNotice({ kind: 'err', text: `测试失败：${String(e instanceof Error ? e.message : e)}` })
    } finally {
      setBusy('')
    }
  }

  // 清除本机保存的 key（daemon 会回落到环境变量里的值）
  const clearKey = async (): Promise<void> => {
    if (!window.confirm('清除本机保存的 key？\n\ndaemon 会回落到环境变量里的同名值（若也没有就视为未配置）。')) return
    setBusy('clear')
    setNotice(null)
    try {
      const r = await saveLlmConfig({ api_key: '' })
      setForm(toForm(r))
      reloadSecrets()
      setNotice({ kind: 'ok', text: '已清除本机保存的 key' })
    } catch (e) {
      setNotice({ kind: 'err', text: `清除失败：${String(e instanceof Error ? e.message : e)}` })
    } finally {
      setBusy('')
    }
  }

  // 离线存 key：daemon 起不来时唯一的自救通道（写 ~/.iwan/secrets.env，明文不出主进程）
  const saveOfflineKey = async (): Promise<void> => {
    setBusy('offline')
    setNotice(null)
    try {
      const r = await window.iwan.setSecret(offlineName.trim(), offlineKey.trim())
      setOfflineKey('')
      reloadSecrets()
      // 存好就催一次拉起：不主动催的话要等重连的低频阶段（最长两分钟）才会再 spawn
      const retried = await window.iwan.retryDaemon().catch(() => false)
      setNotice({
        kind: 'ok',
        text:
          `已存到本机（${r.name}${r.hint}）` +
          (retried ? '，并已请求重新拉起 daemon——连上后端点/模型就能在这里改了。' : '。daemon 下次重试拉起时会读到它。')
      })
    } catch (e) {
      setNotice({ kind: 'err', text: `保存失败：${String(e instanceof Error ? e.message : e)}` })
    } finally {
      setBusy('')
    }
  }

  return (
    <>
      <p className="set-note">
        模型设置由 <b>daemon</b> 持有：保存后会校验、写入 <code>~/.iwan/config.toml</code>（模型与端点）
        和 <code>~/.iwan/secrets.env</code>（API Key），并<b>立即对下一次运行生效</b>。
        环境变量的优先级仍然更高——若某个字段被环境变量（含仓库里的 <code>.env</code>）覆盖，下方会点名。
      </p>
      <datalist id="iwan-model-options">
        {MODEL_SUGGESTIONS.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>

      {notice && (
        <div className={`set-alert ${notice.kind}`}>
          {notice.text}
          {notice.items && notice.items.length > 0 && (
            <ul className="set-alert-list">
              {notice.items.map((it) => (
                <li key={it}>{it}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!connected && (
        <div className="set-alert warn">
          daemon 未连接：端点/模型等 <b>需要 daemon 在线</b>才能保存（它负责校验与落盘）。
          但 <b>API Key 可以先存到本机</b>——缺 key 时 daemon 会在启动期就退出，这是唯一能让它起来的入口。
        </div>
      )}

      {connected && !cfg && (
        <div className="set-alert warn">
          这个 daemon 没有返回模型配置（<code>llm.config.get</code> 不可用）——请让 GUI 与 daemon 用同一版本；
          现在仍可以先存本机 key。
        </div>
      )}

      {connected && form && (
        <>
          <div className="set-row">
            <span className="set-label">协议</span>
            <div className="seg">
              {PROVIDERS.map(([v, label]) => (
                <button key={v} className={form.provider === v ? 'on' : ''} onClick={() => patch({ provider: v })}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="set-row">
            <span className="set-label">Base URL</span>
            <input
              className="set-input grow"
              value={form.baseUrl}
              placeholder="留空 = SDK 默认（api.anthropic.com / OpenAI 默认）"
              onChange={(e) => patch({ baseUrl: e.target.value })}
            />
          </div>
          <div className="set-row set-row-wrap">
            <span className="set-label">快捷填入</span>
            {/* 同时切协议：填了 OpenAI 兼容端点却留着 anthropic 协议，是最常见的 404 来源 */}
            {BASE_URL_PRESETS.map(([label, url, provider]) => (
              <button
                key={label}
                className="mini-btn"
                title={`${url} · ${
                  provider === 'anthropic' ? 'Anthropic 兼容协议' : 'OpenAI 兼容协议'
                }`}
                onClick={() => patch({ baseUrl: url, provider })}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="set-row">
            <span className="set-label">默认模型</span>
            <input
              className="set-input grow"
              list="iwan-model-options"
              value={form.defaultModel}
              placeholder="例如 deepseek-chat"
              onChange={(e) => patch({ defaultModel: e.target.value })}
            />
          </div>
          <div className="set-row">
            <span className="set-label">上下文窗口</span>
            <input
              className="set-input"
              style={{ width: 120 }}
              value={form.contextWindow}
              onChange={(e) => patch({ contextWindow: e.target.value.replace(/[^0-9]/g, '') })}
            />
            <span className="set-value">tokens</span>
          </div>
          <p className="set-note">
            三档模型：<b>留空 = 跟随上面的「默认模型」</b>（当前 {form.defaultModel || '未填'}）；填了就用填的。
            输入框里的灰字是<b>当前实际生效</b>的名字——切档时 daemon 发出去的就是它。
          </p>
          {(
            [
              ['fast', '快速', cfg?.presets?.fast],
              ['balanced', '均衡', cfg?.presets?.balanced],
              ['powerful', '强力', cfg?.presets?.powerful]
            ] as Array<['fast' | 'balanced' | 'powerful', string, string | undefined]>
          ).map(([field, label, resolved]) => (
            <div className="set-row" key={field}>
              <span className="set-label">{label}</span>
              <input
                className="set-input grow"
                list="iwan-model-options"
                value={form[field]}
                placeholder={resolved ?? ''}
                onChange={(e) => patch({ [field]: e.target.value } as Partial<LlmForm>)}
              />
            </div>
          ))}
        </>
      )}

      <div className="set-row">
        <span className="set-label">API Key</span>
        <span className={`set-value${cfg?.api_key_set ? '' : ' dim'}`}>
          {cfg ? keySourceLabel(cfg) : '未知（daemon 未连接）'}
        </span>
      </div>
      <div className="set-row">
        <span className="set-label">变量名</span>
        {connected && form ? (
          <input
            className="set-input"
            style={{ width: 220 }}
            value={form.apiKeyEnv}
            onChange={(e) => patch({ apiKeyEnv: e.target.value })}
          />
        ) : (
          <input
            className="set-input"
            style={{ width: 220 }}
            value={offlineName}
            onChange={(e) => setOfflineName(e.target.value)}
          />
        )}
      </div>
      <div className="set-row set-row-wrap">
        <span className="set-label">{connected ? '新 Key' : 'Key'}</span>
        <input
          className="set-input grow"
          type="password"
          autoComplete="off"
          placeholder="粘贴 key（保存后不回显，只显示尾号）"
          value={connected ? keyDraft : offlineKey}
          onChange={(e) => (connected ? setKeyDraft(e.target.value) : setOfflineKey(e.target.value))}
        />
        {connected ? (
          <>
            <button className="mini-btn" disabled={busy !== '' || !form} onClick={() => void save()}>
              保存
            </button>
            <button className="mini-btn danger" disabled={busy !== ''} onClick={() => void clearKey()}>
              清除
            </button>
          </>
        ) : (
          <button className="mini-btn" disabled={busy !== '' || !offlineKey.trim()} onClick={() => void saveOfflineKey()}>
            存到本机
          </button>
        )}
      </div>
      <div className="set-sub">
        本机密钥文件 <code>{cfg?.secrets_path || '~/.iwan/secrets.env'}</code>
        {secrets.length === 0 ? '：还没有任何密钥' : '：'}
      </div>
      {secrets.map((s) => (
        <div key={s.name} className="set-row row-line">
          <Icon name="shield" size={13} />
          <span className="set-label grow">{s.name}</span>
          <span className="set-value">{s.hint || '已保存'}</span>
          <button
            className="mini-btn danger"
            onClick={() => {
              if (!window.confirm(`从本机密钥文件删除 ${s.name}？`)) return
              void window.iwan
                .deleteSecret(s.name)
                .then(() => {
                  reloadSecrets()
                  setNotice({ kind: 'ok', text: `已从本机删除 ${s.name}` })
                })
                .catch((e) => setNotice({ kind: 'err', text: String(e) }))
            }}
          >
            删除
          </button>
        </div>
      ))}

      {cfg && Object.keys(cfg.env_overrides).length > 0 && (
        <div className="set-alert warn">
          <b>环境变量优先级更高（重启 daemon 后以它们为准）：</b>
          <div className="set-kv">
            {Object.entries(cfg.env_overrides).map(([k, v]) => (
              <div key={k}>
                <code>{k}</code> = <code>{v}</code>
              </div>
            ))}
          </div>
          要让本页设置长期生效：删掉 <code>.env</code> 里对应行，或用同名环境变量统一管理。
        </div>
      )}
      {cfg && (
        <div className="set-sub">
          配置文件 <code>{cfg.config_path}</code> · 当前档位 <b>{cfg.active_preset}</b>
          （{cfg.presets?.[cfg.active_preset] ?? cfg.default_model}）
        </div>
      )}
      {connected && (
        // 吸底操作条：表单比设置弹窗高，滚到一半就找不到"保存"是这类面板最常见的抱怨
        <div className="set-actions">
          <button className="mini-btn primary" disabled={busy !== '' || !form} onClick={() => void save()}>
            {busy === 'save' ? '保存中…' : '保存并应用'}
          </button>
          <button className="mini-btn" disabled={busy !== ''} onClick={() => void test()}>
            {busy === 'test' ? '测试中…' : '测试连接'}
          </button>
          <span className="grow" />
          <span className="set-hint-inline">保存后立即对下一次运行生效</span>
        </div>
      )}
    </>
  )
}

// 引擎区：session.engine_info + 检查点后端（模型/端点已挪到「模型与 API」）
function EngineSection() {
  const [info, setInfo] = useState<Record<string, string> | null>(null)
  useEffect(() => {
    void rpc<Record<string, string>>('session.engine_info', {}).then(setInfo).catch((e) => setInfo({ error: String(e) }))
  }, [])
  const rows: Array<[string, string | undefined]> = [
    ['当前引擎', info?.engine],
    ['检查点后端', info?.checkpoint_backend]
  ]
  return (
    <>
      <p className="set-note">
        引擎在会话级可切（输入框 cpu 选择器，六种执行策略全列）。模型/端点/密钥已独立成
        「模型与 API」分区——那里才能改；这里只看引擎与检查点。
      </p>
      {info === null && <div className="pane-hint">查询 daemon…</div>}
      {rows.filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => (
        <div key={k} className="set-row">
          <span className="set-label">{k}</span>
          <span className="set-value"><code>{String(v)}</code></span>
        </div>
      ))}
      {info?.error && <div className="pane-note">{info.error}</div>}
    </>
  )
}

// 检索质量区：读 ~/.iwan/rag_eval_latest.json（rag.eval --run 落盘）——纯文件桥，零 daemon 协议改动
//
// 【学习要点】这是"只读展示外部产物"的第三种数据源模式（区别于 gui.json 可写、
// trust.list 真命令）：评估由 Python 侧跑（要真打 embedding API，GUI 里不该做），
// GUI 只负责把落盘 JSON 翻成人话。缺文件不报错而是给出生成命令——空态即教程。
interface RagEvalData {
  ts?: string
  root?: string
  embedding_model?: string
  chunk?: { size?: number; overlap?: number }
  index?: { chunks?: number; sources?: number; index_s?: number }
  total_questions?: number
  recall_at_k?: Record<string, number>
  precision_at_k?: Record<string, number>
  mrr?: number
  hit_rate?: number
  category_breakdown?: Record<string, { count?: number; ['avg_recall@5']?: number; hit_rate?: number }>
}

// 百分比格式化（0.875 → "87.5%"；缺值回显 —）
function pct(v: number | undefined): string {
  return v === undefined ? '—' : `${(v * 100).toFixed(1)}%`
}

// 检索质量面板：Recall@K / Precision / MRR / 命中率 + 元信息 + 分类拆解
function QualitySection() {
  const [state, setState] = useState<{ exists: boolean; data: unknown } | null>(null)
  useEffect(() => {
    void window.iwan.readRagEval().then(setState).catch(() => setState({ exists: false, data: null }))
  }, [])
  const d = (state?.exists ? state.data : null) as RagEvalData | null
  const rk = d?.recall_at_k ?? {}
  const pk = d?.precision_at_k ?? {}
  return (
    <>
      <p className="set-note">
        衡量 RAG 检索质量的基准测试：16 个针对本仓库源码的固定问题，看<b>正确文件能否被检回</b>。
        数据来自 <code>~/.iwan/rag_eval_latest.json</code>，由
        <code>uv run python -m iwan_claude.core.rag.eval --run</code> 生成（要真调 embedding API，只在 CLI 侧跑）。
      </p>
      {!state && <div className="pane-hint">读取评估结果…</div>}
      {state && !state.exists && (
        <div className="pane-hint">尚未运行过检索评估——执行 <code>uv run python -m iwan_claude.core.rag.eval --run</code> 后回到本页。</div>
      )}
      {d && (
        <>
          <div className="set-row"><span className="set-label">评估时间</span><span className="set-value">{d.ts ?? '—'}</span></div>
          <div className="set-row"><span className="set-label">Embedding 模型</span><span className="set-value"><code>{d.embedding_model ?? '—'}</code></span></div>
          <div className="set-row"><span className="set-label">索引规模</span><span className="set-value">{d.index?.chunks ?? '?'} 块 / {d.index?.sources ?? '?'} 文件 · 建索引 {d.index?.index_s ?? '?'}s</span></div>
          <div className="set-row"><span className="set-label">题目数</span><span className="set-value">{d.total_questions ?? '—'}</span></div>
          {(['1', '3', '5', '10'] as const).map((k) => (
            <div key={k} className="set-row">
              <span className="set-label">Recall@{k}</span>
              <span className="set-value">{pct(rk[k])}</span>
            </div>
          ))}
          <div className="set-row"><span className="set-label">Precision@5</span><span className="set-value">{pct(pk['5'])}</span></div>
          <div className="set-row"><span className="set-label">MRR（平均倒数排名）</span><span className="set-value">{d.mrr !== undefined ? d.mrr.toFixed(3) : '—'}</span></div>
          <div className="set-row"><span className="set-label">命中率 Hit@10</span><span className="set-value">{pct(d.hit_rate)}</span></div>
          {d.category_breakdown && Object.keys(d.category_breakdown).length > 0 && (
            <>
              <p className="set-note">按题目类别拆解（Recall@5）：</p>
              {Object.entries(d.category_breakdown).map(([cat, v]) => (
                <div key={cat} className="set-row row-line">
                  <span className="set-label grow">{cat}</span>
                  <span className="chg-badge">{pct(v['avg_recall@5'])}</span>
                  <span className="set-value">{v.count ?? '?'} 题</span>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </>
  )
}

// 关于区：core.ping 探活 + 路径速览
function AboutSection() {
  const [pong, setPong] = useState<PongResult | null>(null)
  useEffect(() => {
    void rpc<PongResult>('core.ping', { client: 'gui-settings' }).then(setPong).catch(() => setPong(null))
  }, [])
  return (
    <>
      <div className="set-row"><span className="set-label">协议服务</span><span className="set-value">iwan-core · 127.0.0.1:7437</span></div>
      <div className="set-row"><span className="set-label">daemon 版本</span><span className="set-value">{pong ? pong.server_version : '—（未应答）'}</span></div>
      <div className="set-row"><span className="set-label">运行时长</span><span className="set-value">{pong ? `${Math.floor(pong.uptime_ms / 1000)}s` : '—'}</span></div>
      <div className="set-row"><span className="set-label">数据目录</span><span className="set-value"><code>~/.iwan/</code></span></div>
      <div className="set-row"><span className="set-label">后端配置（只读）</span><span className="set-value"><code>~/.iwan/config.toml</code></span></div>
      <div className="set-row"><span className="set-label">GUI 设置</span><span className="set-value"><code>~/.iwan/gui.json</code></span></div>
      <p className="set-note">iwanclaude · 双进程架构：GUI 与 TUI/CLI 是平级客户端，daemon 是唯一事实源。</p>
    </>
  )
}

export function SettingsView() {
  const open = useGui((s) => s.settingsOpen)
  const setG = useGui((s) => s.set)
  // 分区是 gui.json 之外的状态：顶栏"模型"入口要能直达「模型与 API」，
  // 所以它由 gui store 持有（而不是组件内 useState），openSettings('model') 就是深链
  const sec = useGui((s) => s.settingsSection)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') setG({ settingsOpen: false })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, setG])
  if (!open) return null
  return (
    <div className="set-overlay" onClick={() => setG({ settingsOpen: false })}>
      <div className="set-card" onClick={(e) => e.stopPropagation()}>
        <div className="set-nav">
          <div className="set-brand">
            <Icon name="gear" size={14} /> 设置
          </div>
          {SECTIONS.map(([id, label, icon]) => (
            <button
              key={id}
              className={`set-nav-item${sec === id ? ' active' : ''}`}
              onClick={() => setG({ settingsSection: id })}
            >
              <Icon name={icon} size={14} /> {label}
            </button>
          ))}
        </div>
        <div className="set-body">
          <div className="set-head">
            <span className="grow">{SECTIONS.find(([id]) => id === sec)?.[1]}</span>
            <button className="icon-btn tiny" onClick={() => setG({ settingsOpen: false })} title="关闭 (Esc)">
              <Icon name="x" size={14} />
            </button>
          </div>
          {sec === 'appearance' && <AppearanceSection />}
          {sec === 'projects' && <ProjectsSection />}
          {sec === 'mcp' && <McpSection />}
          {sec === 'trust' && <TrustSection />}
          {sec === 'model' && <ModelSection />}
          {sec === 'engine' && <EngineSection />}
          {sec === 'quality' && <QualitySection />}
          {sec === 'about' && <AboutSection />}
        </div>
      </div>
    </div>
  )
}
