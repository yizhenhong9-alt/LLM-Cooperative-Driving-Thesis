# CoDrivingLLM `highway_env/envs/common/finite_mdp.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下的有限馬可夫決策過程（Finite MDP）轉化檔 `finite_mdp.py`。它負責將連續的車載運動學狀態，投影離散化為以 **TTC (碰撞時間)** 為網格狀態的有限 MDP。

---

## 1. 核心大腦：`finite_mdp` 轉化函數 (Lines 14 - 80)

此函數負責將整個仿真環境打包轉換為一個標準的有限狀態 MDP 機制，包含狀態集、狀態轉移概率和 Reward 機制：

```python
14: def finite_mdp(env: 'AbstractEnv',
15:                time_quantization: float = 1.,
16:                horizon: float = 10.) -> object:
```
* **第 42 行**：`grid = compute_ttc_grid(...)`。調用碰撞時間網格計算函式，獲得當前的離散 TTC 安全邊界。
* **第 45-46 行**：`state = np.ravel_multi_index(grid_state, grid.shape)`。將車輛當前的 `[速度索引, 車道索引, 時間步]` 三維座標，扁平化轉換為一維整數狀態索引（State Index）。
* **第 49-51 行**：計算狀態轉移矩陣 `transition`。使用偏函數 `partial` 綁定計算好的 TTC 網格，確定當前狀態在執行 5 種不同動作（變道/加減速）後，下一幀會滑落到網格的哪個座標。
* **第 53-64 行**：**計算離散狀態獎勵（Reward Function）**：
  $$\text{State Reward} = \text{COLLISION\_REWARD} \times \text{網格碰撞概率} + \text{RIGHT\_LANE\_REWARD} \times \text{靠右比例} + \text{HIGH\_SPEED\_REWARD} \times \text{期望車速比}$$
* **第 71-79 行**：調用外部 `finite_mdp.mdp.DeterministicMDP` 模組，將轉移矩陣、回報值和終止條件組裝成一個確定性的 MDP 模型並回傳。這使得環境可以套用動態規劃（Dynamic Programming）或值迭代（Value Iteration）直接求解最優控制策略。

---

## 2. 碰撞時間網格計算：`compute_ttc_grid` (Lines 81 - 126)

這段程式碼是用於估算碰撞時間矩陣的最核心邏輯：

```python
81: def compute_ttc_grid(env: 'AbstractEnv', ...) -> np.ndarray:
97:     grid = np.zeros((vehicle.SPEED_COUNT, len(road_lanes), int(horizon / time_quantization)))
```
* **第 97 行**：建立一個三維全零網格，其維度分別為：`[速度選擇數, 總車道數, 預測時間長度（Horizon / 步長）]`。
* **第 98-100 行**：遍歷所有可能的自車速度（`speed_index`）與道路上的所有背景車輛（`other`）。
* **第 103-108 行**：**計算碰撞時間（TTC）**：
  * `distance`：計算自車與背景車的縱向安全距離（減去車身的一半長度 `margin`）。
  * `time_to_collision = distance / (ego_speed - other_projected_speed)`。計算相對速度，並相除得到碰撞預計發生的秒數（TimeToCollision）。
* **第 120-124 行**：將算出來的秒數 `time_to_collision` 進行時間離散化取整，並在對應的 `[speed_index, lane, time]` 網格坐標寫入碰撞風險代價 `cost`。這樣大模型或優化器就能一眼看清「我在第 2 條車道，如果加速，將在 3 秒後發生碰撞」的網格分佈。

---

## 3. 狀態轉移運動學模型：`transition_model` (Lines 128 - 166)

此函式模擬了車輛在離散網格中的確定性狀態轉移（例如：左變道動作會使車道索引 `i` 減 1，時間步 `j` 恆加 1）：

```python
128: def transition_model(h: int, i: int, j: int, a: int, grid: np.ndarray) -> np.ndarray:
139:     next_state = clip_position(h, i, j + 1, grid)  # 預設維持原速直行（時間 j + 1）
```
* **第 140-147 行**：
  * 若執行變道（`LANE_LEFT` / `LANE_RIGHT`），車道索引加減一。
  * 若執行加減速（`FASTER` / `SLOWER`），且目前處於當前步（`j == 0`），則速度索引 $h$ 加減一。
* **第 151-165 行**：`clip_position` 函式將新計算出的狀態座標進行邊界裁剪，防止車輛開出車道邊界或超出最大速限，最後使用 `np.ravel_multi_index` 轉換回一維狀態 ID。
