# CoDrivingLLM `highway_env/road/regulation.py` 逐行詳細代碼解析

本文件解讀 `highway_env/road` 目錄下的交通規則約束與路權管理檔 `regulation.py`。它負責定義如何依據車道優先級（Road Priority）與預測碰撞，自動強制車輛讓行或暫停。

---

## 1. 規則約束道路類別：`RegulatedRoad` (Lines 11 - 39)

`RegulatedRoad` 繼承自 `Road`，重寫了 `step` 步進，加入了規則校驗頻率：

```python
21:     def step(self, dt: float) -> None:
22:         self.steps += 1
23:         if self.steps % int(1 / dt / self.REGULATION_FREQUENCY) == 0:
24:             self.enforce_road_rules()
```
* **控制頻率 (Lines 21-25)**：
  在物理步進過程中，並不每幀都執行昂貴的碰撞規則計算。此處設定規則執行頻率 `REGULATION_FREQUENCY = 2`（每秒執行 2 次，即每 0.5 秒執行一次），在符合步數時調用 `enforce_road_rules()`。

```python
27:     def enforce_road_rules(self) -> None:
31:         for v in self.vehicles:
32:             if getattr(v, "is_yielding", False):
33:                 if v.yield_timer >= self.YIELD_DURATION * self.REGULATION_FREQUENCY:
34:                     v.target_speed = v.lane.speed_limit
35:                     delattr(v, "color")
36:                     v.is_yielding = False
```
* **釋放讓行車輛 (Lines 27-39)**：
  遍歷所有車輛。若有車載標記了讓行中（`is_yielding = True`），且讓行計時器超出了最大讓行時長（`YIELD_DURATION`，預設為 0），則釋放該車輛：恢復其目標車速為限速，移除特殊標記顏色，重置讓行狀態。

---

## 2. 衝突路權決策與讓行指派 (Lines 40 - 68)

```python
40:         # Find new conflicts and resolve them
41:         for i in range(len(self.vehicles) - 1):
42:             for j in range(i+1, len(self.vehicles)):
43:                 if self.is_conflict_possible(self.vehicles[i], self.vehicles[j]):
44:                     yielding_vehicle = self.respect_priorities(self.vehicles[i], self.vehicles[j])
45:                     if yielding_vehicle is not None ... :
49:                         yielding_vehicle.target_speed = 0
50:                         yielding_vehicle.is_yielding = True
```
* **衝突判定與強制讓行 (Lines 40-52)**：
  雙重迴圈配對道路上的所有車輛。如果 `is_conflict_possible()` 判定未來有碰撞衝突，則呼叫 `respect_priorities()` 決定誰應該讓行，並**將讓行車的目標速度強行設為 0（強制煞停）**，並將其標記為讓行狀態。

```python
54:     def respect_priorities(v1: Vehicle, v2: Vehicle) -> Vehicle:
62:         if v1.lane.priority > v2.lane.priority:
63:             return v2
64:         elif v1.lane.priority < v2.lane.priority:
65:             return v1
66:         else:  # The vehicle behind should yield
67:             return v1 if v1.front_distance_to(v2) > v2.front_distance_to(v1) else v2
```
* **路權判斷規則（Priority Resolution - Lines 54-68）**：
  * 對稱讀取兩車所處車道的優先權 `lane.priority`。
  * **主線優先**：優先權小的車道車輛，必須讓行給優先權大的車道（例如合流區匝道車 `lane_1` 優先權低，必須讓行給主線車 `lane_0`）。
  * **同級路權**：如果車道優先級相同（如十字路口同為直道），則計算前後距離，後車必須讓行給前車。

---

## 3. 碰撞衝突預測：`is_conflict_possible` (Lines 70 - 84)

這是一套基於運動學預估的快速避障碰撞算法：

```python
70:     def is_conflict_possible(v1: ControlledVehicle, v2: ControlledVehicle, horizon: int = 3, step: float = 0.25) -> bool:
71:         times = np.arange(step, horizon, step)
72:         positions_1, headings_1 = v1.predict_trajectory_constant_speed(times)
73:         positions_2, headings_2 = v2.predict_trajectory_constant_speed(times)
```
* **軌跡預估 (Lines 70-73)**：
  設定預測時界為未來 3 秒，時間步長為 0.25 秒。調用 `predict_trajectory_constant_speed()` 計算兩車在未來 12 個時間點上的預計絕對座標 $[x, y]$ 和朝向角（假設為等速行駛）。
* **幾何碰撞檢測 (Lines 75-83)**：
  * **快速球形粗篩**：如果兩車在某一預估點的直線距離大於車身長度，則快速跳過（節省算力）。
  * **精確矩形精篩**：若直線距離很近，調用 `rotated_rectangles_intersect` 幾何函數。如果兩車在未來軌跡上的 2D 包絡矩形發生重疊相交，代表**可能發生衝突**，回傳 `True`。
