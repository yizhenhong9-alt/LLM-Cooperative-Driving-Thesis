# CoDrivingLLM `llm_controller/llm_agent_negotiation_system.py` 逐行詳細代碼解析

本文件解讀 `llm_controller` 目錄下負責「全域談判協商」的模組檔 `llm_agent_negotiation_system.py`。它扮演了「虛擬交警」的角色，負責在車輛行駛軌跡即將交疊相撞時，調用大模型確定所有衝突車輛的優先通行順序。

---

## 1. 軌跡衝突檢測算法 (Lines 51 - 116)

這是系統在微觀物理層面判定「車輛是否即將相撞」的核心代碼：

```python
77:     def is_conflict(self, env, vehicle_i, vehicle_j):
79:         route_i = self.record_route_xy(env, vehicle_i)
80:         route_j = self.record_route_xy(env, vehicle_j)
```
* **軌跡點收集 (`record_route_xy` - Lines 140-152)**：
  遍歷車輛規劃的全局導航路徑（`vehicle.route`），提取每個路段（直道或圓道）的離散幾何 XY 座標。拼接為一個形狀為 `(point_num, 2)` 的 NumPy 二維陣列，代表這輛車的「未來預計軌跡線」。
* **尋找交會衝突點 (Lines 81-86)**：
  ```python
  points_distance_between_routes = [np.min((route_i[point, 0] - route_j[:, 0]) ** 2 + (route_i[point, 1] - route_j[:, 1]) ** 2) for point in range(len(route_i))]
  distance_between_routes = np.min(points_distance_between_routes)
  ```
  計算車輛 `i` 軌跡線上每個點到車輛 `j` 整個軌跡線的最小歐氏距離。如果兩車軌跡線的最小物理距離**小於 1 米**，判定兩條軌跡線在二維空間中「發生了交叉點（Conflict Point）」。
* **安全反應範圍過濾 (Lines 87-111)**：
  * 計算兩車中心點目前距離該交叉點的直線距離（`distance_to_conflict_point`）。
  * **反應半徑篩選**：如果是在十字路口，反應範圍設為 `50 米`；如果是在高速公路/匝道匯入區，設為 `120 米`。
  * **行駛方向判定**：確認兩車目前是否均朝著交叉點前進（即當前位置到終點的目的地距離大於交叉點到目的地的距離，代表還未通過交會點）。
  * 只有**兩車都身處反應半徑內，且都在朝著交叉點前進**時，才判定這是一個「有效衝突（Conflict）」，回傳衝突狀態與距離。

---

## 2. 虛擬交警談判決策：`send_to_chatgpt` (Lines 154 - 217)

```python
154:     def send_to_chatgpt(self, env, conflict):
160:         conflicting_vehicles_info = []
...
172:         for vehicle_i in range(len(vehicle_list)):
173:             if vehicle_list[vehicle_i] in conflict:
174:                 for vehicle_j in range(vehicle_i):
175:                     if vehicle_list[vehicle_j] in conflict[vehicle_list[vehicle_i]] ... :
...
178:                         conflicting_vehicles_info.append({
179:                              'vehicle_i': vehicle_i_info, 
180:                              'vehicle_i speed': vehicle_i_info.speed,
181:                              'vehicle_i distance to conflict': conflict[vehicle_i_info][vehicle_j_info],
...
```
* **提取雙向衝突組 (Lines 172-182)**：
  篩選出存在雙向碰撞可能的車輛對（如車 `i` 與車 `j`），記錄各自的當前車速、以及各自距離衝突點的米數。
* **談判提示詞組裝 (Lines 184-206)**：
  將提取的衝突組翻譯成文字資訊，並注入虛擬交警 Prompt：
  * *“You are simulating as a traffic police officer overseeing traffic conflicts... For each conflict, decide which vehicle should pass first and which should pass later...”*
  * 強制大模型以標準 JSON 結構輸出通行決定：`"first_vehicle"`, `"second_vehicle"`。
* **調用大模型 (Lines 208-216)**：
  根據環境變數加載 Ollama（預設為 `qwen2.5:7b`）或 OpenAI 接口，發送 Prompt 獲得談判協商結果文本，並與衝突數據一同回傳給執行主程式。
