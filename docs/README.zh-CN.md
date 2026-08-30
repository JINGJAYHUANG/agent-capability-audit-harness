# Agent Capability Audit Harness 中文说明

Agent Capability Audit Harness（Agent 能力审计框架，简称 ACAH）用于回答四个容易被混淆的问题：

1. Agent **声明**具备什么能力；
2. 当前策略**允许、要求确认或拒绝**什么；
3. Adapter（适配器）记录到 Agent **实际做了什么**；
4. 这些结论是否有**可复核证据**。

它不是另一个 Agent，也不是让 Agent 获得更多权限的工具。它是一个测试与审计控制面。

## 核心原则

```text
写在 Prompt 里 ≠ 已经执行
列出工具 ≠ 已经授权
Adapter 说成功 ≠ 已经证明
任务结果看起来正确 ≠ 没有越权
日志存在 ≠ 日志没有被修改
```

ACAH 使用以下结构把这些问题分开：

```text
能力合同
→ Golden Tasks
→ allow / ask / deny
→ 精确审批
→ 行为观察
→ 事件链与制品摘要
→ 通过、失败或回归
```

## 公开演示

公开 Suite 使用 8 个完全虚构的场景：

- 代码库只读审查；
- 白名单网页读取；
- 测试数据库只读查询；
- 文件读取、改名审批和删除拒绝；
- 只起草、不发送、不接受报价；
- 一次与具体参数绑定的批准修改；
- 路径、域名和行数越界；
- 未声明的 root 能力。

共测试 16 个已声明能力和 21 个动作。

## 三种 Adapter

### Fixture

使用固定合成观察结果，适合 CI、回归测试和教学。

### Replay

读取外部 Agent 已记录的观察事件，不在审计环境中启动真实 Agent。

### Command

显式使用 `--allow-command` 后，以参数数组启动外部进程。实现使用 `shell=False`、最小环境变量和超时，但这**不等于沙盒**，也不阻止进程自行联网。

## 运行

```bash
python -m pip install -e .

acah run \
  --contract examples/synthetic/capability-contract.json \
  --suite examples/synthetic/golden-suite.json \
  --adapter examples/synthetic/adapters/reference.json \
  --approvals examples/synthetic/approvals.json \
  --run-dir run-reference \
  --fixed-time 2026-08-30T00:00:00Z

acah verify --run-dir run-reference
```

## 如何理解结果

- `run passed`：这组合同、任务、Adapter 观察和证据满足本次 Suite；
- `verify passed`：运行包内部哈希、事件链和制品完整；
- 两者含义不同。一个失败的能力测试也可以拥有完整、可信的失败证据包。

## 不应做出的结论

不能因为公开 Demo 通过，就声称：

- Codex、Claude Code、OpenClaw 或某个 MCP 已在生产中完全安全；
- 外部进程没有网络访问；
- 模型供应商没有保留数据；
- Agent 永远不会越权；
- 这套规则替代沙盒、操作系统权限、网络隔离或人工审批。

更完整说明见：[架构](architecture.md)、[能力合同](capability-contract.md)、[Golden Tasks](golden-tasks.md)、[Adapter 协议](adapter-protocol.md)、[威胁模型](threat-model.md)和[限制](limitations.md)。
