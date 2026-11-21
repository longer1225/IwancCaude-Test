// 校验重连节奏（纯函数，不依赖 Electron / esbuild 子进程）：
// 快档固定 1s；低频 5→10→20→30s 封顶；之后一直 30s——**永不放弃**。
// 这个性质修的是"daemon 晚于 GUI 起来 → 窗口永远连不上、只能重启"的坑。
//
// 运行：node --experimental-strip-types scripts/test-retry.mjs
// （Node 22 的类型剥离直接 import src/main/retry.ts；比走 esbuild 少一个子进程）
import assert from 'node:assert/strict'

import { DEFAULT_RETRY, retryDelayMs, shouldEnsureDaemon } from '../src/main/retry.ts'

const p = { fastAttempts: 3, fastDelayMs: 1000, baseMs: 5000, maxMs: 30000, ensureEvery: 5 }

// 快档：前 3 次都是 1s
for (const attempt of [1, 2, 3]) assert.equal(retryDelayMs(attempt, p), 1000, `fast#${attempt}`)

// 低频退避：5s → 10s → 20s → 30s(封顶) → 一直 30s
const expected = { 4: 5000, 5: 10000, 6: 20000, 7: 30000, 8: 30000, 50: 30000 }
for (const [attempt, ms] of Object.entries(expected)) {
  assert.equal(retryDelayMs(Number(attempt), p), ms, `backoff#${attempt}`)
}

// 单调不减：不允许退避变小（否则会退化成忙等）
for (let attempt = 2; attempt <= 60; attempt += 1) {
  assert.ok(retryDelayMs(attempt, p) >= retryDelayMs(attempt - 1, p), `monotonic#${attempt}`)
}

// 懒启动时机：首次失败一次；低频阶段每 ensureEvery 次一次（否则 daemon 被杀后没人拉起）
assert.equal(shouldEnsureDaemon(1, p), true)
assert.equal(shouldEnsureDaemon(2, p), false)
assert.equal(shouldEnsureDaemon(9, p), false)
assert.equal(shouldEnsureDaemon(10, p), true)
assert.equal(shouldEnsureDaemon(15, p), true)

// 产品默认值：120 次快档（覆盖冷启动），低频起点 5s、封顶 30s
assert.equal(DEFAULT_RETRY.fastAttempts, 120)
assert.equal(DEFAULT_RETRY.baseMs, 5000)
assert.equal(DEFAULT_RETRY.maxMs, 30000)

console.log('retry schedule OK: fast=1s×120 → 5/10/20/30s 封顶，永不放弃')
