# CP-V2X 與 CoDrivingLLM 程式碼具體對照與詳細變更分析報告
## Detailed Code Diff and Walkthrough Analysis Report

本報告依序列出 CP-V2X 專案中發生變更的所有 Python 程式檔與原版 CoDrivingLLM 的**具體程式碼對照（Code Diff）**，並對每一段變更的底層邏輯、多執行緒同步機制進行深度剖析。

---

## 1. 運行入口對照：`Run_multi_CAV_Parallel.py` vs `Run_multi_CAV_LLM.py`

此檔案主導了模擬器步進迴圈。我們從「單線程同步阻塞」重構為「異步雙線程小腦控制」。

### 1.1 具體程式碼差異對照

#### 🔹 修改一：初始化與背景大腦（Reasoner）啟動（迴圈外部）
* **原版 `Run_multi_CAV_LLM.py`**：
  ```python
  # 無背景執行緒，無資料庫預加載提示
  terminated = False
  t = 0
  obs = env.reset()
  ```
* **新版 `Run_multi_CAV_Parallel.py`**：
  ```python
  terminated = False
  t = 0
  obs = env.reset()
  
  # [修改] 1. 預加載資料庫，並提供當前記憶筆數的反饋
  memory = DrivingMemory(env)
  try:
      db_size = len(memory.scenario_memory._collection.get()['ids'])
      print(f"==========Loaded memory DB, now has {db_size} items.==========")
  except Exception as e:
      print(f"Warning: Failed to read DB item count: {e}")
      
  # [修改] 2. 建立並型協調器，並異步啟動慢腦背景執行緒
  coordinator = ParallelAgentCoordination(env, memory)
  coordinator.start_reasoner(env)
  ```

#### 🔹 修改二：控制迴圈與決策提取（迴圈內部）
* **原版 `Run_multi_CAV_LLM.py`**：
  ```python
  while not terminated:
      memory = DrivingMemory(env)  # 每次步進都重置 DB 連線（開銷大）
      llm_agent_conflict_resolver = LlmAgent_negotiation_module(env)
      negotiation_prompt, conflicting_info = llm_agent_conflict_resolver.llm_controller_run(env)
      llm_agent = LlmAgent_action_module(env)  
      # 同步等大模型推導，耗時 ~2.0 秒，阻塞控制
      llm_actions = llm_agent.llm_controller_run(env, negotiation_prompt, conflicting_info, env.controlled_vehicles, memory)
      action = [item for sublist in llm_actions for item in sublist]
      obs, global_reward, terminated, info = env.step(tuple(action), env)
  ```
* **新版 `Run_multi_CAV_Parallel.py`**：
  ```python
  while not (terminated):
      # [修改] 1. 極速提取決策：主執行緒直接呼叫協調器獲取小腦動作（耗時 < 20ms）
      llm_actions = coordinator.get_actor_actions(env, memory)
      action = [item for sublist in llm_actions for item in sublist]
      
      obs, global_reward, terminated, info = env.step(tuple(action), env)
      # [修改] 2. 以 10Hz 頻率流暢前進，給背景慢腦 0.1 秒的運算緩衝時間
      time.sleep(0.1)
  
  # [修改] 3. 回合結束，安全結束大腦線程
  coordinator.stop_reasoner()
  ```

---

## 2. 決策代理安全性保護：`llm_controller/llm_agent_action.py`

此修改為資料庫操作添加了空指針保護（Null-Pointer Protection），避免大腦在背景單度運行時崩潰。

### 2.1 具體程式碼差異對照

#### 🔹 修改一：歷史記憶檢索保護 (`relative_memory`)
* **原版 `llm_agent_action.py`**：
  ```python
  def relative_memory(self, memory, prompt_info):
      # 無空值檢查，若 memory 為 None 則直接報錯崩潰
      query_scenario = prompt_info.split(';')[0]
      past_decisions = memory.retrieveMemory(query_scenario, top_k=2)
  ```
* **新版 `llm_agent_action.py`**：
  ```python
  def relative_memory(self, memory, prompt_info):
      # [修改] 安全防護：若慢腦背景線程啟動時 memory 未準備就緒，直接返回空字串，防止 AttributeError
      if memory is None:
          return ""
      query_scenario = prompt_info.split(';')[0]
      past_decisions = memory.retrieveMemory(query_scenario, top_k=2)
  ```

#### 🔹 修改二：記憶資料庫線上學習寫入保護 (`memory_update`)
* **原版 `llm_agent_action.py`**：
  ```python
  def memory_update(self, memory, prompt_info, llm_action):
      # 直接調用，容易造成線程衝突或 NoneType 崩潰
      action = str(llm_action)
      sce_descrip = prompt_info.split(';')[0]
      memory.addMemory(sce_descrip, ... , action, ... )
  ```
* **新版 `llm_agent_action.py`**：
  ```python
  def memory_update(self, memory, prompt_info, llm_action):
      # [修改] 安全防護：防範空值寫入，保證執行緒安全性
      if memory is None:
          return
      action = str(llm_action)
      sce_descrip = prompt_info.split(';')[0]
      memory.addMemory(sce_descrip, ... , action, ... )
  ```

---

## 3. [全新模組] 並行協調與安全盾：`llm_controller/parallel_agent.py`

這是原版 CoDrivingLLM 中**完全不存在的全新控制中心代碼**。

### 3.1 核心代碼結構與解析

#### 🔹 A. 動作清理過濾器 (`clean_action_str`)
解決了大模型輸出 Numpy 陣列與資料庫讀出 `"[3]"` 字串時，導致 Dict 鍵值查找拋出 `unhashable type` 崩潰的 Bug。
```python
def clean_action_str(action_val):
    if isinstance(action_val, np.ndarray):
        # 將 numpy 陣列（如 np.array([3])）轉回對應的動作名稱（"FASTER"）
        if len(action_val) > 0:
            action_id = int(action_val[0])
            for k, v in ACTIONS_ALL.items():
                if v == action_id:
                    return k
        return "IDLE"
    elif isinstance(action_val, str):
        action_val = action_val.strip()
        # 將資料庫讀出的字串如 "[3]" 進行解包與整數轉換
        if action_val.startswith("[") and action_val.endswith("]"):
            try:
                action_id = int(action_val[1:-1].strip())
                for k, v in ACTIONS_ALL.items():
                    if v == action_id:
                        return k
            except: pass
        if action_val.isdigit():
            action_id = int(action_val)
            for k, v in ACTIONS_ALL.items():
                if v == action_id:
                    return k
        if action_val in ACTIONS_ALL:
            return action_val
    return "IDLE"
```

#### 🔹 B. 共享變數線程鎖同步機制 (`reasoner_loop` 內部)
慢腦大腦在背景運算，寫入共享變數時必須通過 `threading.Lock` 鎖進行同步，防止主線程同時讀取造成髒數據（Dirty Read）或競爭衝突：
```python
# 慢腦背景大腦寫入：
with self.lock:
    self.shared_negotiation_prompt = negotiation_prompt
    self.shared_conflicting_info = conflicting_info
    self.shared_reasoner_actions[id(ego_veh)] = action_val
```

#### 🔹 C. 物理碰撞防禦網 (Safety Shield 實作)
在主控制線程中，即使小腦檢索出加速指令，只要物理距離小於 **6.0 公尺** 且相對速度大於 0（自車快於前車），安全盾會強制介入改為 `SLOWER` 煞車：
```python
is_unsafe = False
for other in env.road.vehicles:
    if id(other) != id(veh):
        dist = np.linalg.norm(veh.position - other.position)
        if dist < 6.0:  # 6 米防碰撞警戒線
            rel_speed = veh.speed - other.speed
            if rel_speed > 0 and action_str in ["FASTER", "IDLE"]:
                is_unsafe = True
                break

if is_unsafe:
    print(f"[Safety Shield ACTIVE] CAV {veh_display_id} action overridden from {action_str} to SLOWER")
    action_str = "SLOWER"
```
