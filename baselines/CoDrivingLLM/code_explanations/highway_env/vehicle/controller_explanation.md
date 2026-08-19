# CoDrivingLLM `highway_env/vehicle/controller.py` 逐行詳細代碼解析

本文件解讀 `highway_env/vehicle` 目錄下的車輛控制器類別定義檔 `controller.py`。它定義了由高階離散動作驅動、並由雙層 PID 微觀控制器追蹤目標車速與目標車道的受控車載實體。

---

## 1. 雙層受控車輛基底類別：`ControlledVehicle` (Lines 11 - 198)

`ControlledVehicle` 繼承自 `Vehicle`，是實現微觀自適應控制的底層大腦：

* **全局導航路由規劃 (Lines 59-73)**：
  ```python
  def plan_route_to(self, destination: str) -> "ControlledVehicle":
      path = self.road.network.shortest_path(self.lane_index[1], destination)
      self.route = [self.lane_index] + [(path[i], path[i + 1], None) for i in range(len(path) - 1)]
  ```
  * **作用**：當 CAV 被指派目的地節點（如從十字路口南口到西口）時，調用 BFS 演算法求解最短路網節點序列，並將此導航路徑記錄在 `self.route` 中，引導車輛前進。
* **高階宏觀決策解譯 (Lines 75-104)**：
  * 當調用 `act(action)` 傳入語意控制字串時，將其翻譯為目標物理量的轉移：
    * `"FASTER"` / `"SLOWER"` $\rightarrow$ 增減目標期望速度 `self.target_speed`。
    * `"LANE_LEFT"` / `"LANE_RIGHT"` $\rightarrow$ 目標車道 ID 增減一，並藉由 `is_reachable_from()` 安全校驗，更新期望目標車道 `self.target_lane_index`。
* **閉環低階控制器輸出 (Lines 113-152)**：
  * 調用 `steering_control()`，依據當前座標與目標車道中心線橫向误差計算 P 控制，產生期望橫向朝向角，進而解出前輪物理轉向角。
  * 調用 `speed_control()`，依據期望速差輸出物理加速度油門控制量。
* **交匯口轉彎選路 (Lines 171-185)**：
  * 在即將駛入路口前，調用 `get_routes_at_intersection()` 獲取所有可能的轉彎方向拓撲線，更新全局導航路徑。

---

## 2. 離散車速受控車類別：`MDPVehicle` (Lines 199 - 299)

這是為有限馬可夫過程設計的受控車類別（也被 `Run_multi_CAV_LLM.py` 的自駕車預設調用）：

```python
200: class MDPVehicle(ControlledVehicle):
202:     SPEED_COUNT: int = 5   # 速限分級數量
203:     SPEED_MIN: float = 0   # 最小速度為 0 m/s
204:     SPEED_MAX: float = 20  # 最大速度為 20 m/s
```
* **速限離散化投影 (Lines 238-260)**：
  * `index_to_speed`：將離散的速度索引 $[0, 1, 2, 3, 4]$ 轉換為對應的物理車速 $[0, 5, 10, 15, 20]$ m/s。
  * `speed_to_index`：將實時物理車速進行四捨五入，投影到最接近的離散車速分級索引。
* **軌跡前瞻模擬預測 (Lines 276-298)**：
  ```python
  def predict_trajectory(self, actions: List, ...) -> List[ControlledVehicle]:
      v = copy.deepcopy(self)  # 深拷貝一份自車實體
      for action in actions:
          v.act(action)
          for _ in range(...):
              v.step(dt)       # 在隱形沙盒中模擬前進
              states.append(copy.deepcopy(v))
  ```
  * **作用**：當要評估大模型輸出的動作序列時，本函式會複製出一個一模一樣的影子車 `v`，在背景隱形沙盒中虛擬執行動作步進，將預測出的未來座標序列收集並打包。這正是 Pygame 在螢幕上繪製出「預測行車線（車頭前的軌跡細虛線）」的底層物理實現。
