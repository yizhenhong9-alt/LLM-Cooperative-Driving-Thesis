# CoDrivingLLM `highway_env/road/lane.py` 逐行詳細代碼解析

本文件解讀 `highway_env/road` 目錄下的車道幾何與坐標系轉換定義檔 `lane.py`。它負責定義二維世界中的車道拓撲結構，並提供絕對坐標與局部 Frenet 坐標（縱向位置與橫向偏移）之間的幾何變換公式。

---

## 1. 抽象車道基底類別：`AbstractLane` (Lines 10 - 110)

```python
10: class AbstractLane(object):
15:     DEFAULT_WIDTH: float = 4
16:     VEHICLE_LENGTH: float = 5
```
* **第 20-39 行**：定義了所有車道必須實現的兩個核心幾何變換抽象函數：
  * **`position(longitudinal, lateral)`**：
    將車輛局部座標（Frenet 坐標：縱向距離 $s$、橫向偏移 $d$）轉換為物理世界的絕對二維座標 $[x, y]$。
  * **`local_coordinates(position)`**：
    將絕對座標 $[x, y]$ 投影變換回車道局部的 $[s, d]$ 座標，這在計算跟車距離、變道偏移時是必不可少的前提。
* **位置判定 (Lines 61-90)**：
  * `on_lane`：計算車輛橫向偏移是否小於車道半寬（再加上安全裕度 `margin`），且縱向位置落在車道起終點範圍內，判定車輛是否在該車道上。
  * `is_reachable_from`：如果自駕車與本車道的橫向偏離距離小於兩倍車道寬（約 8 米），且非禁止駛入，則判定該車道為**可變道切入目標（Reachable）**。

---

## 2. 直行車道類別：`StraightLane` (Lines 121 - 170)

```python
121: class StraightLane(AbstractLane):
146:         self.heading = np.arctan2(self.end[1] - self.start[1], self.end[0] - self.start[0])
147:         self.length = np.linalg.norm(self.end - self.start)
149:         self.direction = (self.end - self.start) / self.length
150:         self.direction_lateral = np.array([-self.direction[1], self.direction[0]])
```
* **初始化 (Lines 125-154)**：
  * 接收起點與終點坐標，計算車道朝向角 `heading` 和總長度 `length`。
  * 建立車道走向的單位方向向量 `direction`（縱向切線）和橫向法線向量 `direction_lateral`（橫向法線）。
* **座標投影變換 (Lines 155-168)**：
  * `position` 實現極其精鍊的向量運算：
    $$\text{Pos} = \text{Start} + s \cdot \vec{d}_{\text{long}} + d \cdot \vec{d}_{\text{lat}}$$
  * `local_coordinates` 透過與切線/法線方向向量求內積（`np.dot`），將相對位移向量投影拆分為縱向距離 $s$ 與橫向偏離 $d$。

---

## 3. 正弦曲線車道：`SineLane` (Lines 171 - 212)

```python
171: class SineLane(StraightLane):
```
* **作用**：用於合流區（Merge）匝道與主線道的連接。因為一般的直道斜接會產生生硬的角度拐點，正弦車道利用正弦曲線實現緩衝合流。
* **座標變換 (Lines 200-210)**：
  在計算 position 時，橫向偏移會疊加一個正弦偏置量：
  `lateral + self.amplitude * np.sin(self.pulsation * longitudinal + self.phase)`
  朝向角也通過求導加上正弦切線斜率的反正切值，使車輛能夠完美貼合Ｓ型彎道行駛。

---

## 4. 圓弧車道：`CircularLane` (Lines 213 - 260)

```python
213: class CircularLane(AbstractLane):
```
* **作用**：用於十字路口（Intersection）的左轉和右轉車道。
* **幾何推導 (Lines 241-260)**：
  * 接收圓心座標 `center`、半徑 `radius`、起點相位 `start_phase` 與終點相位 `end_phase`。
  * `position` 使用極座標變換公式計算 Cartesian 座標：
    $$\phi = \text{direction} \cdot \frac{s}{R} + \phi_{\text{start}}$$
    $$\text{Pos} = \text{Center} + (R - d \cdot \text{direction}) \cdot [\cos\phi, \sin\phi]^T$$
  * `local_coordinates` 則反向計算位移向量的模長以求得半徑偏離量 $d$，並調用 `np.arctan2` 計算弧度得到縱向行駛距離 $s$。
