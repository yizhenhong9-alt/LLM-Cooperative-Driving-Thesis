# Actor-Reasoner `train.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下的主訓練循環與數據生成檔 `train.py`。

---

## 1. 數據記錄與 Excel 開啟功能 (Lines 29 - 67)

```python
29: def open_excel(i):
30:     file_dir = './train/' + Scenario_name + '/excel/' + strftime("%Y-%m-%d", ...
```
* **第 29-41 行**：在 `./train/{Scenario_name}/excel/` 資料夾下，以當前日期建立一個以 case ID 命名的 Excel 工作簿，用於保存車輛行駛軌跡。

```python
50: def write_data(workbook, vehicles, llm_output, if_passed, t):
...
59:         state = [round(vehicle.x, 2), round(vehicle.y, 2), round(vehicle.speed, 2), ...]
60:         row_data = [t, round(vehicle.x, 2), round(vehicle.y, 2), round(vehicle.speed, 2), ...]
```
* **第 50-67 行**：在每個時間步 `t`，將自車 CAV 與對手車 HDV 的物理座標、車速、加速度、朝向角、剩餘距離、駕駛風格以及大模型做出的 HMI 意圖語句、動作命令寫入工作簿中對應的 Sheet 頁面，並保存。

---

## 2. 模擬器初始化與多案列運行 (Lines 69 - 101)

```python
69: class Simulator:
70:     def __init__(self, case_id):
71:         self.cav_info, self.hdv_info = tools.initialize_vehicles()
```
* **第 69-80 行**：調用 `initialize_vehicles()` 隨機發配自駕車 CAV 與不同行車風格的背景博弈車 HDV，加載大模型 Agent 與 Chroma 記憶庫。

```python
87:         ani = FuncAnimation(self.fig, self.update, interval=10, frames=Sim_times, blit=False, repeat=False, save_count=Sim_times)
88:         video_dir = f'./train/{Scenario_name}/video/' + strftime("%Y-%m-%d", gmtime()) + suffix + '/'
...
91:         ani.save(video_dir + str(self.case_id) + '.gif', dpi=50)
```
* **第 81-101 行**：**動態 GIF 可視化保存**：
  使用 matplotlib `FuncAnimation` 綁定更新函數 `update`，設定仿真步數上限為 200 幀。在背景將每一步的車載渲染畫面保存，最後編譯壓製輸出為高質量的 `.gif` 動態行車軌跡圖。

---

## 3. 單幀更新與雙車步進：`update` (Lines 103 - 128)

這段代碼驅動每一步的物理與智能演化：

```python
103:     def update(self, frame):
104:         if tools.if_passed_conflict_point(self.cav_info, self.hdv_info):
105:             self.llm_output[0] = 'FASTER'
106:         else:
107:             self.llm_output = self.agent.llm_run(self.llm_output, self.instruction_info, self.cav_info, self.hdv_info, self.memory)
```
* **決策判斷 (Lines 104-108)**：
  如果已經通過衝突交點，自車進入完全直道行駛，強行設為 `'FASTER'`。若尚未通過，則調用 `agent.llm_run()`：這會引導大模型進行 CoT 推理，計算最佳決策，並將新碰撞反思經驗寫入記憶庫。

```python
110:         controller = IDM(self.cav_info, self.hdv_info, self.llm_output[0])
111:         ego_acc = controller.cal_acceleration()
112:         temp_cav_info = tools.kinematic_model(self.cav_info, ego_acc)
```
* **自駕車步進 (Lines 110-112)**：
  實例化 IDM 控制器，代入大模型做出的動作 `llm_output[0]`（如 FASTER/SLOWER），解出物理加速度，調用單車運動學模型前進一步。

```python
114:         bayesian_agent = Bayesian_Agent(self.hdv_info, self.cav_info, action_type='discrete')
115:         temp_hdv_info = bayesian_agent.update_state()
116:         self.hdv_info, self.cav_info = temp_hdv_info, temp_cav_info
```
* **對手車博弈步進 (Lines 114-124)**：
  實例化貝氏博弈代理人 `Bayesian_Agent`。求解當前局勢下的 Bayesian Nash 均衡動作，驅使人類駕駛車前進一步。最後更新兩車狀態，繪製最新的 2D 地圖並將數值記錄存檔。
* 系統通過 `for case in range(50)` 循環連續運行 50 個不同的發車案例，累積大量的 ChromaDB 持久化安全經驗。
