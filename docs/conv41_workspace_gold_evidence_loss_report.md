# Conv-41：Segment 口径下“召回了但没有保留证据”分析报告

## 本次变更（关键）

- 已将 `workspace_execute_recall` 的语义改为 **Segment 粒度**：
  - 不再以 Episode 命中作为 workspace 召回命中标准；
  - 改为 `dialogue_id:episode_id:segment_id` 映射到 `Dk:x` 后再判定命中。
- 变更位置：`scripts/run_locomo/run_eval_locomo.py`

重算结果（conv-41）：

- `overall_recall = 0.885197`（final evidence 口径，不变）
- `overall_workspace_execute_recall = 0.918...`（由原先 episode 宽松口径下降）
- 满足条件 `memory_agent_recall == 0 && memory_agent_workspace_execute_recall > 0` 的题目：
  - 由 7 题降到 6 题：`Q3, Q8, Q31, Q52, Q64, Q82`
  - `Q41` 被剔除（说明它此前的“命中”主要是 episode 粗粒度带来的乐观估计）

---

## 筛选条件与判定标准

- 条件 A：`memory_agent_workspace_execute_recall > 0`（Segment 口径下确实召回过支持 gold 的 segment）
- 条件 B：`memory_agent_recall == 0`（最终 evidence 没命中 gold）
- 解释：这组题是“检索阶段命中过，最终保留阶段没留下”。

---

## 逐题分析（Segment 口径）

### Q3 — What type of volunteering have John and Maria both done?

- 结果：`workspace_execute_recall=0.5`, `recall=0.0`
- gold：`D3:5`, `D2:1`
- 命中的 segment：`dlg_locomo10_conv-41_3:ep_001:seg_001`
- 生命周期：
  - `seen_in_execute_rounds = [3]`
  - `in_useful_rounds = []`
  - `in_kept_after_judge_rounds = []`
- 因果：该命中 segment 在执行池出现过，但从未被 judge 选为 useful，随后在 `prune_except(useful ∪ new)` 逻辑下未进入保留集。
- 问题：命中过但未晋升为可保留证据，属于“执行命中 -> judge 筛选断链”。

### Q8 — What might John's financial status be?

- 结果：`workspace_execute_recall=1.0`, `recall=0.0`
- gold：`D5:5`
- 命中的 segment：`dlg_locomo10_conv-41_5:ep_001:seg_001`
- 生命周期：
  - `seen_in_execute_rounds = [1,2,3]`
  - `in_useful_rounds = [1,2]`
  - `in_kept_after_judge_rounds = [1,2]`
  - 最终轮保留：否
- 因果：前两轮曾被判 useful 并保留，但第三轮 query 漂移后 useful 集合发生替换，旧证据被覆盖式裁剪掉。
- 问题：典型“先保住、后丢失”。

### Q31 — When did John get his dog Max?

- 结果：`workspace_execute_recall=1.0`, `recall=0.0`
- gold：`D17:1`
- 命中的 segment：`dlg_locomo10_conv-41_17:ep_001:seg_001`
- 生命周期：
  - `seen_in_execute_rounds = [1,2]`
  - `in_useful_rounds = []`
  - `in_kept_after_judge_rounds = [1]`
  - 最终轮保留：否
- 因果：judge 两轮 `useful_ids` 均为空，系统退化到“按 new 替换”，导致第一轮保住的命中证据在第二轮被覆盖。
- 问题：<span style="color:#B91C1C;"><b>Judge 的产出结果解析失败</b></span> 触发破坏性更新。

### Q52 — Who have written notes of gratitude to Maria?

- 结果：`workspace_execute_recall=1.0`, `recall=0.0`
- gold：`D27:8`, `D21:19`
- 命中的 segment：
  - `dlg_locomo10_conv-41_21:ep_001:seg_004`
  - `dlg_locomo10_conv-41_27:ep_001:seg_002`
- 生命周期：
  - `seen_in_execute_rounds = [1,2]`
  - `in_useful_rounds = []`
  - `in_kept_after_judge_rounds = [1]`
  - 最终轮保留：否
- 因果：和 Q31 同型，judge 输出为空后触发覆盖式替换，第二轮把第一轮命中证据清掉。
- 问题：保留链路对 <span style="color:#B91C1C;"><b>Judge 的产出结果解析失败</b></span> 过敏。

### Q64 — What job might Maria pursue in the future?

- 结果：`workspace_execute_recall=0.75`, `recall=0.0`
- gold：`D32:14`, `D5:8`, `D11:10`, `D27:4`
- 命中的 segment：
  - `dlg_locomo10_conv-41_11:ep_001:seg_003`
  - `dlg_locomo10_conv-41_27:ep_001:seg_002`
  - `dlg_locomo10_conv-41_5:ep_001:seg_002`
- 生命周期：
  - `seen_in_execute_rounds = [2,3]`
  - `in_useful_rounds = []`
  - `in_kept_after_judge_rounds = []`
  - 最终轮保留：否
- 因果：命中过的 segment 没有被 judge 认定 useful，始终无法进入保留集。
- 问题：执行命中与 judge 选择目标不一致。

### Q82 — What did John receive a certificate for?

- 结果：`workspace_execute_recall=1.0`, `recall=0.0`
- gold：`D9:2`
- 命中的 segment：`dlg_locomo10_conv-41_9:ep_001:seg_001`
- 生命周期：
  - `seen_in_execute_rounds = [1,2]`
  - `in_useful_rounds = []`
  - `in_kept_after_judge_rounds = [1]`
  - 最终轮保留：否
- 因果：第一轮短暂保留，第二轮在 judge 空 useful 输出下被替换掉。
- 问题：与 Q31/Q52 同模式，触发点是 <span style="color:#B91C1C;"><b>Judge 的产出结果解析失败</b></span>。

---

## 机制结论（Segment 口径下仍成立）

1. 硬覆盖裁剪是主因  
   `prune_except(useful ∪ new)` 使历史正确证据没有“存活保护”。

2. judge 空 useful 输出是高危触发器  
   一旦 useful 为空，保留策略会退化成“只看新证据”，容易把已命中的旧证据清掉。

3. Segment 口径验证了此前判断  
   误报减少（Q41退出候选），但“召回命中 -> 最终不保留”的真实问题依然明显存在。

---

## 建议（本轮）

1. P0：Judge 异常保护  
   `useful_ids` 为空或解析失败时，禁止 destructive prune，冻结上一轮 kept。

2. P0：命中锚点保护  
   命中过 gold-like 证据后，后续轮次默认保护，不因 query 改写自动丢弃。

3. P1：持续保留 Segment 指标  
   `workspace_execute_recall` 固定采用 segment 口径；episode 仅作辅助统计，不作主指标。

4. P1：增加生命周期监控  
   记录 `seen_in_execute` / `in_useful` / `in_kept_after_judge` / `in_final`，定位具体丢失阶段。

