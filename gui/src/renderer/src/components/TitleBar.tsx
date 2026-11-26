// 自绘顶栏：无边框窗口的"标题栏替身"——品牌区 + 拖拽区 + 窗口控制三键
//
// 【学习要点】1) Electron 无边框窗口没有系统标题栏，拖拽/双击最大化靠 CSS
// `-webkit-app-region: drag` 让操作系统把这块区域当标题栏处理——但 drag 区域内
// 所有可交互元素（按钮）必须显式 no-drag，否则点击被窗口移动吞掉。2) 最大化
// 按钮的图标要随窗口状态换（最大化⇄还原），状态用"事件推送 + 挂载补查"双通道
// 拿：推送可能错过挂载前的变化，补查保证初值正确——与连接状态同一套模式。
import { useEffect, useState } from 'react'
import { useStore, setModelPreset } from '../store'
import { useGui } from '../guiHelpers'
import { Popover, MenuItem } from './Popover'
import { Icon } from './Icon'

// 10x10 描边矢量：笔画粗细/端点全部对齐 Windows 11 标题栏图标的观感
function GlyphMin() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <path d="M0 5h10" stroke="currentColor" strokeWidth="1" />
    </svg>
  )
}
function GlyphMax() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" strokeWidth="1" />
    </svg>
  )
}
// 还原态：两个错位方块（Win11 样式）
function GlyphRestore() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <rect x="0.5" y="2.5" width="7" height="7" fill="none" stroke="currentColor" strokeWidth="1" />
      <path d="M2.5 2.5V0.5h7v7H7" fill="none" stroke="currentColor" strokeWidth="1" />
    </svg>
  )
}
function GlyphClose() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <path d="M0 0l10 10M10 0L0 10" stroke="currentColor" strokeWidth="1" />
    </svg>
  )
}
// 新窗口：一扇小窗 + 右上角加号（"再开一路"的直觉形状）
function GlyphNew() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
      <rect x="0.5" y="2.5" width="7" height="7" fill="none" stroke="currentColor" strokeWidth="1" />
      <path d="M6 0.5v3M4.5 2h3" stroke="currentColor" strokeWidth="1" />
    </svg>
  )
}

// 模型档位中文名（与 Composer 的模型 chip 同一套词汇）
const PRESET_LABELS: Array<[string, string]> = [
  ['fast', '快速'],
  ['balanced', '均衡'],
  ['powerful', '强力']
]

// 模型名压缩显示：去掉 vendor 前缀，超长截断（顶栏只有 38px 高，塞不下全名）
function shortModel(name: string): string {
  if (!name) return ''
  const tail = name.split('/').pop() ?? name
  return tail.length > 24 ? `${tail.slice(0, 23)}…` : tail
}

// 顶栏"换模型"入口：不需要先有会话（档位在 daemon 侧本来就是全局单例），
// 点开三档 + 一条直达「模型与 API」的深链——这就是用户要的"换模型的 GUI 入口"
function ModelChip() {
  const cfg = useStore((s) => s.llmConfig)
  const status = useStore((s) => s.status)
  const openSettings = useGui((s) => s.openSettings)
  const [busy, setBusy] = useState(false)
  const current = cfg
    ? shortModel(cfg.presets?.[cfg.active_preset] ?? cfg.default_model)
    : status === 'connected'
      ? '…'
      : '未连接'

  // 切档：失败回弹提示（daemon 侧权限/校验问题不该被吞掉）
  const pick = (preset: string): void => {
    setBusy(true)
    void setModelPreset(preset)
      .catch((e) => window.alert(`切换失败：${String(e instanceof Error ? e.message : e)}`))
      .finally(() => setBusy(false))
  }

  return (
    <Popover
      className="tb-model-pop"
      anchor={(open) => (
        <button
          className={`tb-model${busy ? ' busy' : ''}`}
          title="换模型（全局设置，下一次运行起生效）"
          onClick={open}
        >
          <Icon name="sparkle" size={12} />
          <span className="tb-model-name">{current}</span>
          <Icon name="chevronDown" size={11} />
        </button>
      )}
    >
      {(close) => (
        <>
          <div className="pop-title">模型 · 全局切换（下一次运行起生效）</div>
          {PRESET_LABELS.map(([id, label]) => (
            <MenuItem
              key={id}
              label={label}
              hint={cfg?.presets?.[id] ?? ''}
              active={cfg?.active_preset === id}
              onClick={() => {
                close()
                pick(id)
              }}
            />
          ))}
          <div className="menu-sep" />
          <MenuItem label="配置模型与 API Key…" hint="设置" onClick={() => { close(); openSettings('model') }} />
        </>
      )}
    </Popover>
  )
}

// 外部 daemon 提示：连到的 daemon 不属于本仓库时，标题栏常驻一枚警示 chip
// 【为什么放标题栏】状态条只在断线时出现；"连到别人"恰恰是连着的时候最危险——
// 改代码不生效、权限/回滚都作用在别人的进程上。常驻才能一直被看见（BUG-3）
function ExternalDaemonChip() {
  const identity = useStore((s) => s.daemonIdentity)
  const status = useStore((s) => s.status)
  if (!identity.external || status !== 'connected') return null
  return (
    <span
      className="tb-external"
      data-testid="external-daemon-chip"
      title={`${identity.message}\n当前仓库：${identity.localRoot}`}
    >
      <Icon name="alert" size={12} />
      <span className="tb-external-text">外部 daemon</span>
    </span>
  )
}

export function TitleBar() {
  const [maximized, setMaximized] = useState(false)

  // 初值补查 + 变化订阅：挂载时窗口可能早已最大化（重启 GUI 的场景）
  useEffect(() => {
    void window.iwan.winIsMaximized().then(setMaximized)
    return window.iwan.onWinMaximized(setMaximized)
  }, [])

  return (
    <header className="titlebar">
      <span className="tb-brand">
        <span className="tb-mark" aria-hidden="true" />iwan work
      </span>
      <ModelChip />
      <ExternalDaemonChip />
      <span className="tb-drag" />
      <button
        className="tb-btn"
        title="新窗口（另开一路并行任务）"
        onClick={() => window.iwan.newWindow()}
      >
        <GlyphNew />
      </button>
      <button
        className="tb-btn"
        title="最小化"
        onClick={() => window.iwan.winMinimize()}
      >
        <GlyphMin />
      </button>
      <button
        className="tb-btn"
        title={maximized ? '向下还原' : '最大化'}
        onClick={() => window.iwan.winToggleMaximize()}
      >
        {maximized ? <GlyphRestore /> : <GlyphMax />}
      </button>
      <button className="tb-btn tb-close" title="关闭" onClick={() => window.iwan.winClose()}>
        <GlyphClose />
      </button>
    </header>
  )
}
