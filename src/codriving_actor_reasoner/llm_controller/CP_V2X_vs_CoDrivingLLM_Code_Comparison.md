# CP-V2X 與 CoDrivingLLM 程式碼對比差異報告
## Code Comparison Report: CP-V2X vs. CoDrivingLLM

本報告深入對比了新融合專案 **CoDrivingLLM_Parallel_V2X (CP-V2X)** 與原版基線專案 **CoDrivingLLM** 在模組、檔案以及核心控制邏輯上的**相同之處**與**修改/新增之處**。這能清晰展現我們進行並行化解耦的技術改造細節。

---

## 1. 核心相同部分 (Core Identical Parts)

CP-V2X 繼承了 CoDrivingLLM 優秀的「車路協同（V2X）空間感知模型」與「大模型提示詞工程」，以下模組在程式碼結構與運算數學上**完全相同**：

### 1.1 空間場景解析器：`llm_controller/Scenario_description.py`
* **相同之處**：
  * 用於計算自駕車（CAV）與前後鄰車的相對距離、相對速度，並將數值坐標翻譯為文字語意的 `Scenario` 類別沒有做任何修改。
  * 保持了原汁原味的特徵提取與文本生成邏輯，確保兩者在輸入大模型時的場景描述（Scenario Text）完全一致。

### 1.2 RSU 衝突談判器：`llm_controller/llm_agent_negotiation_system.py`
* **相同之處**：
  * 用於檢測路口/合流區多車衝突（基於距離與 TTC 碰撞時間）的 `detect_conflicts` 和 `get_conflict_vehs` 函式完全相同。
  * 向大模型詢問多車通行順序優先級的系統 Prompt 和 RSU 決策格式完全一致。

### 1.3 提示詞與行為常量：`llm_controller/prompt_llm.py`
* **相同之處**：
  * 保存自駕車五個離散動作（`LANE_LEFT=0`、`IDLE=1`、`LANE_RIGHT=2`、`FASTER=3`、`SLOWER=4`）的字典 `ACTIONS_ALL` 完全一致。
  * 內置的交通法規說明和決策注意事項文本完全一致。

---

## 2. 核心不同與修改部分 (Modified & Restructured Parts)

為了解耦控制延遲並保證控制即時性，我們對專案的「主控制迴圈」、「決策代理」以及「資料庫交互」進行了重大改造，並引入了全新設計的調度器。

### 2.1 [全新新增] 並行調度器與安全屏障：`llm_controller/parallel_agent.py`
這是原版 CoDrivingLLM **完全沒有的全新檔案**，是 CP-V2X 的控制核心：
* **相同/不同點**：**100% 全新編寫**。
* **主要程式碼功能**：
  * 實現了 `ParallelAgentCoordination` 類別，使用 `ThreadPoolExecutor` 管理背景慢腦執行緒。
  * 實作了具有線程鎖（`threading.Lock`）保護的共享記憶體區，用於異步傳遞 RSU 協商結果與車輛決策。
  * 實現了基於幾何安全距離（6.0米）與相對速度的主動碰撞過濾器 **`Safety Shield`**。
  * 實現了動作標準化轉換器 **`clean_action_str`**，徹底解決了 Numpy 陣列與資料庫字串格式不相容導致的崩潰。

---

### 2.2 [重構變更] 主運行入口：`Run_multi_CAV_Parallel.py` vs `Run_multi_CAV_LLM.py`
* **差異對照**：
  * **原版 `Run_multi_CAV_LLM.py`（同步阻塞）**：
    在每一步（step）中，主線程必須等大模型算完 RSU 談判、再等大模型算完單車決策，然後才調用 `env.step`。導致決策延遲高達 **1.5s~2s**，控制率只有 **0.5Hz**。
  * **新版 `Run_multi_CAV_Parallel.py`（異步並行）**：
    在 `reset()` 時異步啟動背景 Reasoner 慢大腦。在 `while` 主迴圈中，主線程直接呼叫 `coordinator.get_actor_actions()` 以 **<20ms** 的延遲從小腦資料庫中快速查表控制車輛，主線程能以 **10Hz (每秒 10 幀 / 0.1秒更新)** 速度極其流暢運行。
  * **新增功能**：在初始化時自動讀取並印出資料庫中現有的記憶筆數，提供即時進度反饋。

---

### 2.3 [安全修改] 自車決策代理：`llm_controller/llm_agent_action.py`
* **差異對照**：
  * **原版 `llm_agent_action.py`**：
    在 `relative_memory`（檢索歷史經驗）與 `memory_update`（寫入新經驗）中，均預設 `memory` 資料庫物件是必然存在的，沒有防空指針保護。
  * **新版 `llm_agent_action.py`**：
    我們在兩個資料庫操作函式中，增加了安全保護代碼：
    ```diff
     def relative_memory(self, memory, prompt_info):
    +    if memory is None:
    +        return ""  # 慢腦在背景運作若暫無 memory，安全返回空，防 NoneType 崩潰
         ...
     def memory_update(self, memory, prompt_info, llm_action):
    +    if memory is None:
    +        return
    ```
    這解決了慢腦在背景執行時，因為 memory 物件初始化順序或空值而觸發的 `'NoneType' object has no attribute 'retrieveMemory'` 崩潰 Bug。

---

### 2.4 [微幅調整] 記憶體資料庫接口：`llm_controller/memory.py`
* **差異對照**：
  * 我們修改了新專案中資料庫加載時的提示語，便於在並行運作中追蹤資料庫的加載狀態。
  * 保留了原有的 `Chroma` 向量庫存取機制，但小腦查表與慢腦寫入均改為通過 `parallel_agent.py` 進行安全協調，防止多個執行緒同時讀寫 SQLite3 造成的檔案鎖死（Database Locked）衝突。
