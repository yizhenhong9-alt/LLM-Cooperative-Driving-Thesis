# CoDrivingLLM `highway_env/envs/common/observation.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下的環境狀態觀測與特徵提取檔 `observation.py`。它負責收集物理引擎中的車輛座標、速差等特徵，為大模型或強化學習模型提供結構化狀態輸入。

---

## 1. 視覺灰階像素觀測：`GrayscaleObservation` (Lines 44 - 90)

```python
44: class GrayscaleObservation(ObservationType):
80:         new_obs = self._record_to_grayscale()
88:         raw_rgb = self.env.render('rgb_array')
89:         return np.dot(raw_rgb[..., :3], self.config['weights'])
```
* **作用**：當自駕車不使用結構化座標、而是使用電腦視覺（Computer Vision）作為輸入時調用。
* **物理提取 (Lines 80-89)**：
  * 調用 `self.env.render('rgb_array')` 獲取當前模擬視窗的 RGB 像素畫布。
  * 乘以灰度轉換矩陣 `weights` 將彩圖降維成灰階圖，再利用 `np.roll` 將多幀像素疊加（Stack），輸出給卷積神經網絡（CNN）。

---

## 2. 【最核心】車身運動學觀測：`KinematicObservation` (Lines 124 - 227)

這是自駕大模型專案中**唯一被實體使用**的觀測器類型：

```python
124: class KinematicObservation(ObservationType):
128:     FEATURES: List[str] = ['presence', 'x', 'y', 'vx', 'vy']
```
* **觀測空間 (Line 164)**：返回一個 Box 二維矩陣，維度為 `[觀察車輛上限數, 特徵數]`。
* **物理狀態提取 (Lines 194-227)**：
  1. **獲取自車狀態**：讀取自駕車本體的座標與速度，存入第一列。
  2. **獲取周圍鄰車**：
     `close_vehicles = self.env.road.close_vehicles_to(..., count=vehicles_count-1)`
     調用物理道路接口，獲取感知距離內最近的車輛。
  3. **相對坐標系轉換**：
     `v.to_dict(origin)`
     如果不是絕對座標模式，鄰車的 x, y 將自動減去自車的 x, y。**這將座標系轉化為以「自車為原點 (0,0)」的相對座標系**（例如前方鄰車 x = 20 代表在前 20 米，橫向 y = -4 代表在左側車道），這極大地降低了大模型理解幾何空間的難度。
  4. **填充缺失數據**：如果感知到的車輛不足 15 輛，剩餘的列以全零 `np.zeros` 填充（代表無車）。

---

## 3. 多胞形佔據網格：`OccupancyGridObservation` (Lines 229 - 280)

```python
229: class OccupancyGridObservation(ObservationType):
234:     GRID_SIZE: List[List[float]] = [[-5.5*5, 5.5*5], [-5.5*5, 5.5*5]]
235:     GRID_STEP: List[int] = [5, 5]
```
* **作用**：將自駕車周邊劃分為 $5 \times 5$ 的物理二維網格空間。
* **物理提取**：檢測每個格子的物理範圍內是否被其它車輛佔據（Occupied）。如果被佔據，在該網格中標記 `presence = 1` 以及其相對速差。這常用於經典的局部路徑避障規劃。

---

## 4. 多智能體狀態包裝器：`MultiAgentObservation` (Lines 362 - 402)

```python
362: class MultiAgentObservation(ObservationType):
```
* 同 `MultiAgentAction` 的結構類似。此類別遍歷每一輛受控自駕車（CAV），為其各自實例化一個獨立的 `KinematicObservation`。
* 它將所有自駕車所感知到的局部環境特徵拼裝為一個元組（Tuple），支援了 `Run_multi_CAV_LLM.py` 在多車環境下調用 `obs = env.reset()` 或 `obs, ... = env.step()` 獲取並行多車狀態數據。
