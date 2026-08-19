# CoDrivingLLM `highway_env/envs/common/mdp_controller.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下的車輛雙層控制器核心代碼 `mdp_controller.py`。它負責接收大模型的宏觀語意決策，將其翻譯為微觀物理量（油門加速度與轉向角），並基於單車運動學模型進行步進模擬。

---

## 1. 離散動作解析與目標轉換 (Lines 22 - 58)

`mdp_controller(vehicle, env_copy, action)` 是該控制器的主要入口：

* **加減速決策解析 (Lines 34-43)**：
  * 當大模型輸出加速指令 `3` (FASTER)：
    `speed_index = speed_to_index(vehicle.speed) + 1`
    將當前速度索引加一，並通過 `index_to_speed` 將目標速度設為下一個速度區間（以 5 m/s 為步長）。
  * 減速指令 `4` (SLOWER) 反之，將目標速度索引減一。
* **左右變道決策解析 (Lines 45-57)**：
  * 當執行右變道 `2` (LANE_RIGHT) 或左變道 `0` (LANE_LEFT) 時：
    `target_lane_index = _from, _to, np.clip(_id + 1, ...)`
    獲取目標車道 ID，並調用 `is_reachable_from` 物理接口，判斷自駕車當前的橫向位置是否具備切換至目標車道的空間。如果可行，則修改自駕車的期望目標車道 `vehicle.target_lane_index`。

---

## 2. 微觀縱橫向閉環控制器 (Lines 110 - 150)

在設定好目標車道與速度後，系統通過比例（P）控制器計算方向盤與油門：

### A. 橫向比例控制（Steering Control - Lines 110-138）
這是一個二階疊加的橫向 PID 控制器：
1. **橫向位置控制**：根據車輛與目標車道中心線的橫向誤差（`lane_coords[1]`），乘以比例係數 `KP_LATERAL`，產生橫向速度指令：
   `lateral_speed_command = - KP_LATERAL * lane_coords[1]`
2. **轉向角映射**：將橫向速度指令轉換為期望朝向角 `heading_ref`，並與自車當前朝向做差，通過比例控制器計算轉向速率，最後利用車身長度 $L$ 映射為前輪物理轉向角 `steering_angle`：
   `steering_angle = np.arcsin(LENGTH / 2 / speed * heading_rate_command)`

### B. 縱向比例控制（Speed Control - Lines 141-150）
縱向跟車油門計算極其簡明：
```python
149: return KP_A * (target_speed - vehicle.speed)
```
* 利用目標速度與當前車速的差值，乘以增益 `KP_A`（預設為 $1/0.6 \approx 1.67$），得到下一步的期望油門加速度。

---

## 3. 車輛狀態物理積分更新 (Lines 64 - 74)

```python
67:     beta = np.arctan(1 / 2 * np.tan(delta_f))
68:     v = vehicle.speed * np.array([np.cos(vehicle.heading + beta),
69:                                   np.sin(vehicle.heading + beta)])
70:     vehicle.position += v * dt
71:     vehicle.heading += vehicle.speed * np.sin(beta) / (LENGTH / 2) * dt
72:     vehicle.speed += action['acceleration'] * dt
```

* **運動學單車模型（Kinematic Bicycle Model）**：
  * 計算車身側偏角 `beta`。
  * 通過當前車速 `vehicle.speed` 乘以三角函數，將速度分解為二維空間 X 軸與 Y 軸的分量，並乘以時間步長 `dt` 累加更新車輛位置座標。
  * 累加更新車輛 朝向角（Heading）與車速，將新座標記錄於軌跡軌記歷史 `vehicle.trajectories` 中，完成該 Step 的物理世界步進。
