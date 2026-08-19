# Actor-Reasoner `params.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下的全局超參數與靜態路網映射設定檔 `params.py`。

---

## 1. 全局仿真參數與駕駛風格權重 (Lines 4 - 14)

```python
4: # Scenario name
5: Scenario_name = 'roundabout'
```
* **第 5 行**：`Scenario_name`：設定當前仿真地圖。可修改為 `'intersection'` (十字路口)、`'merge'` (匯入匝道) 或 `'roundabout'` (環島)。

```python
7: Action_space = np.array([[0, 0], [2, 0], [-2, 0], [-4, 0]])
8: Action_length = len(Action_space)
9: Target_speed = [10, 10, 8]
```
* **第 7-9 行**：
  * `Action_space`：定義車輛的離散控制集，格式為 `[縱向加速度, 橫向動作]`。例如 `[-4, 0]` 代表緊急煞車，`[2, 0]` 代表全力加速。
  * `Target_speed`：定義三種駕駛風格的期望目標時速 $[10, 10, 8]$ m/s（對應：激進、正常、保守）。

```python
10: Weight_hv = [[1.56, 0, 8.33, 3.69], [1.72, 0, 8.2, 5.7], [2.1, 0, 7.79, 8.44]]  # agg nor con
11: Acceleration_list = [0, 2, -2, -4, 0, 0]
13: Dt = 0.1
```
* **第 10-13 行**：
  * **`Weight_hv`**：**經典博弈論效用權重矩陣**：
    分別代表 `[激進, 正常, 保守]` 三種人類駕駛的效用偏好權重。其四個維度對應博弈論收益項：`[1. 車道偏離懲罰, 2. 效率速度收益, 3. 終點距離進度, 4. TTC碰撞懲罰]`。例如，激進型（agg）對 TTC 碰撞的重視度（最後一項 `3.69`）遠低於保守型（con）的 `8.44`。
  * `Dt = 0.1`：設定仿真控制步長為 0.1 秒（10Hz 運行）。

---

## 2. 三大地圖路網連通性關係 (Lines 15 - 46)

本段靜態編碼了十字路口、合流區、環島引道與出口之間的拓撲映射，用作 BFS 選路與衝突判定：

```python
18: INTERSECTION_POSSIBLE_ENTRANCE = ['n2', 'n3', 'e2', 'e3', 's2', 's1', 'w2', 'w1']
19: INTERSECTION_ENTRANCE_EXIT_RELATION = {'n2': ['w2', 's2', 's3'], ...}
```
* 以 Dictionary 定義在特定入口進入路口時，可達的合法出口（如從北側南行二線道 `n2` 進入，可以前往西出口 `w2`、南出口 `s2` 或 `s3`）。

```python
29: if Scenario_name == 'intersection':
30:     POSSIBLE_ENTRANCE = INTERSECTION_POSSIBLE_ENTRANCE
...
32:     STOP_LINE = {'n2':70, 'n3':70, 'e2':70, 'e3':70, ...}
```
* 根據開局設定的 `Scenario_name`，自動切換載入對應的入口集合、連通性字典、以及停止線的幾何距離位置 `STOP_LINE`。
