# Think-life 运行时规格

本文档是 Think-life 运行时的权威说明（与实现计划同步）。评测探针路径不在本规格范围内。

## 不变量

1. 一切刺激经 Perception 入队；**入队即触发调度**（`ThreadDrainer`），不依赖旁路 `busy` 标志。
2. 用户可见文本必须可追溯到 `reply_to_user` tool。
3. `execution_feedback` 必须带 `delegate_id` + `transaction_id`。
4. WM 按 `transaction_id` 隔离。
5. Scene 按 `thread_id` 时间序 append，不按事务切块。
6. Think 由调度器驱动，非单次 HTTP handle。

## 队列与运行时相位（OS 语义）

`effective_depth = inbox_pending + (1 if in_flight else 0)`（在途指已 pop、尚未跑完的刺激）。`pending_stimuli` 在 **pop 后** 与 **入队后** 立即按真实 inbox 刷新，避免「已 pop 仍计 pending」导致刚发一条 user 就误报 `busy`。

| effective_depth | runtime_phase | 含义 |
|-----------------|---------------|------|
| 0 | `ready` | 无排队、无在途 |
| 1 | `processing` | 恰好一个刺激在被消费 |
| ≥2 | `busy` | 有 backlog |

- `thread_runtime.busy`（think_life）：`effective_depth >= 2`（兼容字段）。
- UI 处理中指示：建议用 `runtime_phase !== 'ready'`（含 `processing` 与 `busy`）。
- **日程**：与用户消息相同，lease 后 **仅入队** HEARTBEAT 刺激；不在 heartbeat 层因 `busy` 推迟 lease。`mark_running` / `mark_done` 在对应 transaction 开始/终态时回调 schedule store。

## 抢占（`scheduler.preempt_enabled`）

- `false`：当前刺激完整消费后才处理下一条；新 user 刺激归入当前 active user transaction。
- `true`：更高优先级刺激入队可协作式取消正在执行的 `ExecutionAgent`（`stream` + `cancel_event`），被打断刺激 **重新入队**（`max_preempt_per_stimulus` 上限，默认 3）。

## 核心实体

见 `src/m_agent/runtime/think_life/contracts.py`。

## Scene

跨事务、按 `occurred_at` 排序的 append-only log；`transaction_id` 仅作标签。

持久化：`data/memory/chat-api/<owner>/scene/<thread_id>.jsonl`。

## 事务生命周期

`pending` → `running` → `waiting_execution` → `running` → `completed|failed|cancelled`；可 `suspended`（抢占）。

**User 事务段（与 flush 对齐）**：同一 `thread_id` 上，两次成功 **memory flush** 之间，所有 `USER_MESSAGE`（及该 txn 上的 `execution_feedback`）归入 **同一条** `USER_TASK`；`reply_to_user` 定稿 **不会** 结束 user 事务。`flush_thread` 成功时调用 `on_flush_segment`，将 active user txn 置为 `completed` 并清空 active 指针；下一句 user 刺激再新建 txn。`SCHEDULE` 事务仍在该次提醒处理完成后结束。

## WM

仅 `TransactionRecord.wm_entries`；Think 读 WM + Scene tail；Work 经 WMDisplay 读当前 CPU 事务 WM。

## Think 层（plan-only）

启用 `runtime.profile: think_life` 时，`ThinkingAgent.max_executions_per_turn` 在运行时置为 `0`：Think **只规划**，不在 Think 内调用 ExecutionAgent。工具执行与 `reply_to_user` 均由 `ThinkLifeLoop._delegate_and_wait` 委托；工具结束后入队 `execution_feedback`，再 plan 一轮并定稿回复。`execution_feedback` 规划时从 Scene 取最近 user utterance 作为 `pending_user_request`。

## 配置

`chat_controller.yaml` → `runtime.profile: think_life` 与 `runtime.think_life` 块。

## HTTP：运行中输入与 Scene

- `POST /v1/chat/threads/{thread_id}/stimuli`：用户消息入队（202），不阻塞 HTTP；每 thread 至多一个 `ThreadDrainer` 后台线程调用 `run_thread` 直至 inbox 清空。
- `GET /v1/chat/threads/{thread_id}/scene`：只读 Scene 时间轴（`limit` / `before_seq`）。
- Thread SSE：`stimulus_queued`、`reply_emitted`、`scene_entry_appended`、`thread_runtime_updated`。
- `GET .../schedules/heartbeat` 与 `GET /healthz` 含 `thread_runtime`（含 `runtime_phase`、`effective_depth`）/ `think_life` 健康字段。
- Legacy profile 下 `schedule_busy_retries_total` 仍可能因 `thread_runtime.busy` 推迟 lease；**think_life** 日程不走该门控。
