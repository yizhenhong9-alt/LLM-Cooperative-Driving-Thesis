# CoDrivingLLM 原始專案 `Run_multi_CAV_LLM.py` 逐行詳細代碼解析

本文件針對 `CoDrivingLLM` 專案的入口主程式 `Run_multi_CAV_LLM.py` 進行逐行、逐段的功能解析，幫助您深入理解其運行時的資料流與仿真邏輯。

---

## 1. 模組導入與環境初始化 (Lines 1 - 10)

```python
1: from llm_controller.llm_agent_action import *
2: from llm_controller.llm_agent_negotiation_system import *  # system perspective negotiation
3: from llm_controller.memory import DrivingMemory
4: import highway_env
5: import imageio
6: import openpyxl
7: import os
8: import shutil
9: 
10: os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
```

* **第 1-3 行**：從子資料夾 `llm_controller` 中導入自駕車控制模組（`llm_agent_action`）、路側 RSU 衝突談判模組（`llm_agent_negotiation_system`）以及 Chroma 記憶體資料庫接口（`memory`）。
* **第 4-8 行**：導入仿真環境 `highway_env`、影片寫入庫 `imageio`、Excel 處理庫 `openpyxl`、系統操作庫 `os` 與檔案複製工具 `shutil`。
* **第 10 行**：設定環境變數 `KMP_DUPLICATE_LIB_OK = "TRUE"`。這是為了防止 PyTorch/SentenceTransformers 在本地多核心 CPU 上運行 OpenMP 庫時，因為多個副本衝突而導致 Python 直譯器直接閃退（Crash）。

---

## 2. Excel 初始化助手：`open_excel` (Lines 12 - 24)

此函式負責在指定回合（Episode）開始前，建立或讀取用於保存車輛軌跡數據的 Excel 檔案。

```python
12: def open_excel(i):
13:     file_dir = './llm_controller/excel/' + '/'
14:     file_name = file_dir + str(i) + '.xlsx'
15: 
16:     if not os.path.exists(file_dir):
17:         os.makedirs(file_dir)
18:     workbook = openpyxl.Workbook()
19:     if os.path.exists(file_name):
20:         workbook = openpyxl.load_workbook(file_name)
21: 
22:     # if 'Sheet' in workbook.sheetnames:
23:     #     del workbook['Sheet']
24:     return file_name, workbook
```

* **第 12-14 行**：接收參數 `i`（當次回合編號），定義存儲目錄為 `./llm_controller/excel/`，檔案名為 `{i}.xlsx`。
* **第 16-17 行**：檢查資料夾是否存在，若無則呼叫 `os.makedirs` 自動建立遞迴目錄。
* **第 18-20 行**：新建一個 openpyxl 的 `Workbook` 工作簿物件。如果硬碟中已存在同名檔案，則使用 `load_workbook` 將其讀入以供續寫或覆蓋。
* **第 24 行**：回傳建立好的檔案路徑與工作簿物件。

---

## 3. 軌跡數據寫入模組：`write_data` (Lines 26 - 46)

此函式在每個模擬步進（Step）執行，收集當前所有車輛的物理狀態，寫入 Excel。

```python
26: def write_data(workbook, env, t):
27:     column_names = ['t', 'x', 'y', 'v', 'theta', 'background_veh?']
28:     for vehicle in env.road.vehicles:
29:         sheet_name = str(vehicle.id)
30:         if sheet_name not in workbook.sheetnames:
31:             worksheet = workbook.create_sheet(sheet_name)
32:             worksheet.append(column_names)
33:         else:
34:             worksheet = workbook[sheet_name]
35:         controlled_vehicles = env.controlled_vehicles
36:         if vehicle not in controlled_vehicles:
37:             background_vehicles = False
38:         else:
39:             background_vehicles = True
```

* **第 26-27 行**：接收工作簿、環境變數與當前步進時間 `t`。設定資料行名稱包括：時間、X坐標、Y坐標、車速、朝向角、以及是否為背景車。
* **第 28-34 行**：遍歷仿真道路上的所有車輛。以每台車的唯一 `vehicle.id` 作為 Excel 分頁名稱（Sheet Name）。如果分頁不存在則新建並寫入表頭；若已存在，則獲取該分頁的物件指標。
* **第 35-39 行**：檢查該車輛是否包含在受控自駕車列表 `env.controlled_vehicles` 中。若非，代表它是模擬器內建 IDM 控制的背景人類駕駛車（`background_vehicles = False`）；若是，則為受控自駕車（`True`）。

```python
40:         state = [round(vehicle.position[0], 2), round(vehicle.position[1], 2), round(vehicle.speed, 2), round(vehicle.heading, 2), background_vehicles]
41:         row_data = [t, round(vehicle.position[0], 2), round(vehicle.position[1], 2), round(vehicle.speed, 2), round(vehicle.heading, 2), background_vehicles]
42:         worksheet.append(row_data)
43:         worksheet.cell(row=t + 2, column=1, value=t)
44:         for i, item in enumerate(state):
45:             worksheet.cell(row=t + 2, column=i + 2, value=item)
46:     return workbook
```

* **第 40-42 行**：將車輛的位置、速度、朝向角進行小數點兩位四捨五入，封裝入當前時間步 $t$ 的狀態清單並寫入分頁。
* **第 43-45 行**：使用 openpyxl 逐格定位，將 `t` 寫入第一行，並將狀態寫入隨後的列中。
* **第 46 行**：返回已寫入當前幀數據的工作簿物件。

---

## 4. 仿真環境宣告 (Lines 48 - 58)

```python
48: # if choose merge, active config
49: config = {
50:     "simulation_frequency": 20,
51:     "policy_frequency": 5,
52:     "duration":40
53: }
54: 
55: # env = gym.make('merge-multi-agent-v0', config=config)
56: # env = gym.make('intersection-multi-agent-v0')
57: env = gym.make('highway-v0')
```

* **第 49-53 行**：設定高速公路模擬器的頻率參數。物理模擬頻率為 20Hz（每秒步進 20 次），決策刷新頻率為 5Hz（每秒大模型更新 5 次），單次回合時長上限為 40 秒。
* **第 55-57 行**：宣告仿真環境。註解部分展示了合流區（`merge-multi-agent-v0`）與十字路口（`intersection-multi-agent-v0`）的加載法；第 57 行正式啟用了直行高速公路（`highway-v0`）場景。

---

## 5. 主回合循環與同步阻塞決策 (Lines 60 - 107)

```python
60: for i in range(20, 100):
61:     video_path = './llm_controller/video/' + str(i) + '.mp4'  
62:     writer = imageio.get_writer(video_path, fps=30) 
63:     file_name, workbook = open_excel(i)
64:     terminated = False
65:     t = 0
66:     obs = env.reset()
```

* **第 60-63 行**：開始外層回合循環（此處設定補跑第 20 ~ 99 回合）。初始化影像寫入器保存為 `.mp4` 影片，並打開 Excel 工作簿。
* **第 64-66 行**：重設碰撞標記 `terminated = False`，時間步計數器 `t = 0`，並初始化仿真場景物理世界（`env.reset()`）。

```python
67:     while not (terminated):
68:         print('---------------------------------------------------------------')
69:         # memory module
70:         memory = DrivingMemory(env)
71: 
72:         # negotiation module
73:         llm_agent_conflict_resolver = LlmAgent_negotiation_module(env)  # system perspective negotiation
74:         negotiation_prompt, conflicting_info = llm_agent_conflict_resolver.llm_controller_run(env)
```

* **第 67-70 行**：進入內層時間步迴圈，直到車輛碰撞或抵達終點。在每一步開始時，實例化 `DrivingMemory`，這會直接在硬碟中連接 SQLite3 客戶端。
* **第 72-74 行**：**車路協商（同步阻塞 1）**：建立路側單元 RSU 協商代理，同步調用大模型進行優先級協商。主線程此時卡死，直到 Ollama 回傳車輛讓行建議。

```python
76:         # decision
77:         llm_agent = LlmAgent_action_module(env)  
78:         sce = llm_agent.retrun_sce()  # sce data
79:         llm_actions = llm_agent.llm_controller_run(env, negotiation_prompt, conflicting_info, env.controlled_vehicles, memory)  # negotiation results from upper layer and conflict info which stores distance speed
```

* **第 76-80 行**：**單車決策（同步阻塞 2）**：建立決策模組代理。將剛才路側協商得到的優先級建議（`negotiation_prompt`）、衝突距離資訊以及記憶庫物件傳入。此時主線程**再次卡死**，等待大模型推導出車輛的動作。

```python
82:         action = [item for sublist in llm_actions for item in sublist]  # [[1], [3]]->[1, 3]
83: 
84:         for veh in env.controlled_vehicles:
85:             print(veh, veh.speed)
86: 
87:         obs, global_reward, terminated, info = env.step(tuple(action), env)
88:         env.render()
89:         print("llm_actions:", action)
90:         print("global_reward_llm:", global_reward)
```

* **第 82-87 行**：將所有受控車輛的二維動作列表（例如 `[[1], [3]]`）扁平化為一維元組（`(1, 3)`），並傳遞給 `env.step` 驅動車輛在模擬器中前進。
* **第 88-90 行**：渲染模擬器畫面，並印出當前步進中大模型的決策動作與全域回報值。

```python
92:         frame = env.render('rgb_array')
93:         writer.append_data(frame)
94: 
95:         workbook = write_data(workbook, env, t)
96:         workbook.save(file_name)
97:         t += 1
```

* **第 92-97 行**：將物理模擬器渲染出的圖像陣列（RGB Array）寫入影片檔。調用前述的 `write_data` 寫入當前物理軌跡數據並實時存檔到硬碟。時間步 `t` 累加 1。

```python
103:         env.render()
104:     writer.close()
105:     print(i)
```

* **第 104-105 行**：當單次 Episode 結束（碰撞或超時），關閉影片寫入器，完成該回合影片的封裝，並列印當前回合 ID，準備進入下一輪。
