# CoDrivingLLM `highway_env/vehicle/kinematics.py` 逐行詳細代碼解析

本文件解讀 `highway_env/vehicle` 目錄下的車輛運動學模型基礎檔 `kinematics.py`。它負責定義二維剛體車輛在物理引擎中的運動更新與碰撞檢測幾何。

---

## 1. 車輛類別與初始化：`Vehicle` (Lines 16 - 54)

```python
16: class Vehicle(object):
24:     COLLISIONS_ENABLED = True  # 預設開啟碰撞檢測
27:     LENGTH = 5.0  # 車身長度為 5 米
29:     WIDTH = 2.0   # 車身寬度為 2 米
```
* **初始化屬性 (Lines 36-54)**：
  * `position` / `heading` / `speed`：車輛的絕對座標、朝向角、速度物理量。
  * `lane_index` / `lane`：當前距離車身最近的車道拓撲位置。
  * `crashed`：記錄車輛是否撞毀。一旦撞毀，車輛會亮起紅燈，動作輸入會被接管為急煞車。
  * `history`：雙向隊列 `deque`，儲存過去 30 個時間步的車身狀態（軌跡歷史），用於渲染車輛軌跡。

---

## 2. 運動學單車模型物理更新：`step` (Lines 122 - 141)

這是車輛物理位置更新的核心：

```python
122:     def step(self, dt: float) -> None:
132:         self.clip_actions()
133:         delta_f = self.action['steering']
134:         beta = np.arctan(1 / 2 * np.tan(delta_f))
135:         v = self.speed * np.array([np.cos(self.heading + beta),
136:                                    np.sin(self.heading + beta)])
137:         self.position += v * dt
138:         self.heading += self.speed * np.sin(beta) / (self.LENGTH / 2) * dt
139:         self.speed += self.action['acceleration'] * dt
```
* **一階運動學單車模型（Kinematic Bicycle Model）**：
  * `delta_f`：前輪轉向角。
  * `beta`：質心側偏角。公式為：$\beta = \arctan(\frac{1}{2} \tan(\delta_f))$。
  * **坐標累加**：沿著質心側偏角與朝向角之和（`self.heading + beta`）方向計算速度分量，並對位置座標、朝向角與車速進行一階 Euler 數值積分（乘以時間步長 `dt`），步進車身。

---

## 3. 包絡矩形碰撞檢測：`check_collision` (Lines 174 - 209)

這段程式碼檢測車子與周圍障礙物/車輛是否發生撞擊：

```python
174:     def check_collision(self, other: Union['Vehicle', 'RoadObject']) -> None:
```
* **車輛間碰撞 (Lines 183-189)**：
  如果檢測到與另一台 Vehicle 發生物理重疊碰撞：
  `self.speed = other.speed = min([self.speed, other.speed], key=abs)`
  **碰撞物理懲罰**：將兩台相撞車的速強制同步為兩者中較慢的那個（模擬剛性碰撞阻尼），並將兩者的 `crashed` 標記置為 `True`。
* **碰撞幾何檢測算法 (Lines 201-209)**：
  * **快速球形預檢（Spherical Pre-check）**：計算兩車中心點歐氏距離。如果大於車身長度（5 米），說明絕不可能相撞，直接回傳 `False`（節省 90% 的矩形重疊計算開銷）。
  * **精確旋轉矩形相交檢測（Rotated Rectangles Intersection）**：如果距離很近，呼叫幾何算法 `rotated_rectangles_intersect`（考慮兩車各自的長度、寬度、與旋轉朝向角），精準判定包絡矩形是否重合。
