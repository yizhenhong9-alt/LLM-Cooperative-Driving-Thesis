# Walkthrough: Parallel_V2X_v2 (Style-Aware V2X Cooperative System)

我們已經成功在 `遠端桌面實驗/CoDrivingLLM_Parallel_V2X_v2/` 中建立了 **V2 版本子專案**。本專案融合了人類駕駛風格辨識、記憶分割數據庫（ChromaDB）檢索、以及動態安全裕度（Safety Shield）調整。

---

## 🛠️ 修改檔案與核心邏輯說明

### 1. 記憶分割資料庫
* **修改檔案**: [memory.py](file:///c:/Users/user/Desktop/CoDrivingLLM/遠端桌面實驗/CoDrivingLLM_Parallel_V2X_v2/llm_controller/memory.py)
* **邏輯**:
  - `DrivingMemory` 現在會加載三個獨立的 ChromaDB 數據集：`normal`、`aggressive`、和 `conservative`，分別存儲在 `./db/{env_id}/{style}/` 下。
  - `retrieveMemory` 和 `addMemory` 會自動使用正則表達式從描述中解析出 `Interaction vehicle driving style`，並自動寫入/讀取對應的風格分區。

### 2. Style 與 Intention 的推理與解析
* **修改檔案**: [llm_agent_action.py](file:///c:/Users/user/Desktop/CoDrivingLLM/遠端桌面實驗/CoDrivingLLM_Parallel_V2X_v2/llm_controller/llm_agent_action.py)
* **邏輯**:
  - 更新大腦 Reasoner `send_to_chatgpt` 的 Prompt，使其步步思考周圍人類背景車的**意圖**（Intention: ACCELERATE/DECELERATE）和**風格**（Style: AGGRESSIVE/CONSERVATIVE）。
  - 新增 `extract_output` 函數，實時解析大模型返回的 JSON 輸出，提取意圖、風格和自車決策。
  - 將最新預測出的風格和意圖追加到對比描述中，使得檢索（Retrieval）和寫入（Memory Update）能正確尋找對應的記憶分區。

### 3. 動態安全邊界與並行協調
* **修改檔案**: [parallel_agent.py](file:///c:/Users/user/Desktop/CoDrivingLLM/遠端桌面實驗/CoDrivingLLM_Parallel_V2X_v2/llm_controller/parallel_agent.py)
* **邏輯**:
  - 新增線程安全的 `shared_reasoner_styles` 變量，用於將背景大腦（Reasoner）識別的風格實時同步給前端小腦（Actor）。
  - 前端 Actor 在運行 `get_actor_actions` 時，依據目前識別的鄰車風格去特定的記憶分區檢索動作。
  - **動態安全盾 (Safety Shield)**：
    - 如果對手車輛風格為 **AGGRESSIVE** ➜ 安全避障距離調大到 **8.0 米**。
    - 否則 ➜ 安全避障距離保持標準的 **5.0 米**。

### 4. 主入口更新
* **修改檔案**: [Run_multi_CAV_Parallel.py](file:///c:/Users/user/Desktop/CoDrivingLLM/遠端桌面實驗/CoDrivingLLM_Parallel_V2X_v2/Run_multi_CAV_Parallel.py)
* **邏輯**:
  - 更新啟動時的資料庫大小查詢，分別打印出三種風格資料庫的已存儲數量。

---

## 🚀 如何在遠端桌面運行實驗

請依循以下步驟以 `codriving` 虛擬環境啟動模擬：

1. 開啟遠端桌面的命令提示字元 (CMD) 或 PowerShell。
2. 啟動 Conda 虛擬環境：
   ```bash
   conda activate codriving
   ```
3. 切換至 V2 版本子專案目錄：
   ```bash
   cd c:\Users\user\Desktop\CoDrivingLLM\遠端桌面實驗\CoDrivingLLM_Parallel_V2X_v2
   ```
4. 啟動模擬腳本：
   ```bash
   python Run_multi_CAV_Parallel.py
   ```
