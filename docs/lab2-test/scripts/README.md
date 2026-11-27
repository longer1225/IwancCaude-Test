# 双实例与隔离环境脚本（首轮执行前用）

> 用途：一条命令把**两份副本（7438 / 7439）**起起来，并把 6 个数据变量改道到仓库内临时目录，
> 避免测试写用户目录。对应《测试计划》6.1 环境与数据安全、2.3 已知限制。
> 适用：12-07 首轮执行、12-10 回归（尤其 BUG-2 的双实例验证）。

## 一、怎么用

```powershell
# 在仓库根执行（会占用 7438 / 7439 两个端口）
powershell -ExecutionPolicy Bypass -File docs\lab2-test\scripts\start-two-instances.ps1

# 只想起一个（7438）：
powershell -ExecutionPolicy Bypass -File docs\lab2-test\scripts\start-two-instances.ps1 -Single

# 停掉本脚本起的所有实例并清理：
powershell -ExecutionPolicy Bypass -File docs\lab2-test\scripts\start-two-instances.ps1 -Stop
```

脚本做的事：

1. 在 `runs/evidence/<日期>/` 下建隔离目录（trace / memory / sessions / policy / trust / plugins / secrets）；
2. 复制一份仓库到 `runs/instance-b/`（仅当要双实例时），把它的 `.env` 端口改成 7439；
3. 分别用 `uv run iwan core start` 起两个 daemon，并用 `core status` 打印结果；
4. 把 PID 与端口写进 `runs/evidence/<日期>/instances.json`，供后续脚本/清理使用；
5. `-Stop` 时按记录逐个 `core stop` 并删除临时实例副本。

## 二、验证要点（对应 BUG-2 的验收）

```powershell
# A（7438）在跑时，对 B（7439）执行 stop，A 必须仍然 running
cd runs\instance-b
uv run iwan core stop
cd ..\..
uv run iwan core status        # 期望仍为 running (127.0.0.1:7438)
```

## 三、注意

- 脚本不会改你的用户级 `~/.iwan`，所有数据都在 `runs/` 下（已被 gitignore）；
- 若 7438/7439 已被占用，脚本会先探测并提示，不会强行杀进程；
- 首次运行 `uv sync` 可能较慢；GUI 冒烟（SM-01）不在此脚本范围内。
