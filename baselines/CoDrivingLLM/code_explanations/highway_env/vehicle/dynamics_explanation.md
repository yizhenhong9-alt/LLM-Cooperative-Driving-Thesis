# CoDrivingLLM `highway_env/vehicle/dynamics.py` 逐行詳細代碼解析

本文件解讀 `highway_env/vehicle` 目錄下的車輛動力學模型檔 `dynamics.py`。與基礎運動學模型不同，本檔實現了考慮輪胎側偏、側向受力以及路面摩擦阻力的二階動態單車模型（Rajamani 2011 經典理論）。

---

## 1. 動力學模型參數與初始化 (Lines 11 - 32)

```python
11: class BicycleVehicle(Vehicle):
17:     MASS: float = 1  # 歸一化車身質量 [kg]
18:     LENGTH_A: float = Vehicle.LENGTH / 2  # 前軸至質心距離 a [m]
19:     LENGTH_B: float = Vehicle.LENGTH / 2  # 後軸至質心距離 b [m]
20:     INERTIA_Z: float = 1/12 * MASS * (Vehicle.LENGTH ** 2 + 3 * Vehicle.WIDTH ** 2)  # 繞 Z 軸轉動慣量 [kg.m2]
21:     FRICTION_FRONT: float = 15.0 * MASS  # 前輪側向輪胎剛度剛度/摩擦力 [N]
```
* **初始化狀態 (Lines 27-32)**：
  除了基礎的 XY 坐標，本模型額外維護兩個動態狀態量：
  * `lateral_speed`：**側向滑移速度**（$v_y$，即垂直車身走向的橫滑速度）。
  * `yaw_rate`：**偏航角速度**（$r$ 或 $\dot{\psi}$，即轉向旋轉速率）。

---

## 2. 輪胎側滑受力與微分求解：`derivative` (Lines 44 - 70)

這是計算動力學核心狀態導數（導函數）的實現：

```python
52:         theta_vf = np.arctan2(self.lateral_speed + self.LENGTH_A * self.yaw_rate, self.speed)  # 前輪側偏角
53:         theta_vr = np.arctan2(self.lateral_speed - self.LENGTH_B * self.yaw_rate, self.speed)  # 後輪側偏角
54:         f_yf = 2*self.FRICTION_FRONT * (delta_f - theta_vf)  # 前輪側向力 (2.25)
55:         f_yr = 2*self.FRICTION_REAR * (delta_r - theta_vr)   # 後輪側向力 (2.26)
```
* **輪胎側偏角與側向力 (Lines 52-55)**：
  * 計算前輪側偏角 `theta_vf` 和後輪側偏角 `theta_vr`（基於橫滑速度、角速度與前/後軸長度）。
  * 計算前/後輪胎所承受的側向剛度恢復力 $F_{yf}$ 和 $F_{yr}$。當轉向過急或速度過快時，側偏角會增大，輪胎側向力會反向抵抗，產生逼真的漂移橫滑物理現象。

```python
59:         d_lateral_speed = 1/self.MASS * (f_yf + f_yr) - self.yaw_rate * self.speed  # 側向加速度 (2.21)
60:         d_yaw_rate = 1/self.INERTIA_Z * (self.LENGTH_A * f_yf - self.LENGTH_B * f_yr)  # 偏航角加速度 (2.22)
```
* **牛頓第二定律與轉矩微分**：
  * 側向滑移加速度（`d_lateral_speed`）由側向力之和除以質量，再減去向心力分量（$\dot{v}_y = \frac{F_{yf} + F_{yr}}{m} - r \cdot v_x$）得到。
  * 偏航角加速度（`d_yaw_rate`，即轉向扭矩加速度 $\dot{r}$）由力矩之和除以轉動慣量得到。

---

## 3. 狀態步進更新：`step` (Lines 91 - 100)

```python
91:     def step(self, dt: float) -> None:
94:         self.position += derivative[0:2, 0] * dt
95:         self.heading += self.yaw_rate * dt
96:         self.speed += self.action['acceleration'] * dt
97:         self.lateral_speed += derivative[4, 0] * dt
98:         self.yaw_rate += derivative[5, 0] * dt
```
* 同樣使用一階 Euler 積分。
* 除了位置、朝向和縱向車速外，它還實時更新**側滑速度與偏航角速度**。這使車輛在急彎變道時能體現出輪胎打滑、側滑甩尾等真實車輛動態。此動力學模型常用於強化學習在極限避障或惡劣天氣（如冰雪路面）下的安全控制測試。
