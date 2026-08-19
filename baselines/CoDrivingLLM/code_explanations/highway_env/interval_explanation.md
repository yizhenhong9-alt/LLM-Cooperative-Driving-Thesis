# CoDrivingLLM `highway_env/interval.py` 逐行詳細代碼解析

本文件解讀 `highway_env` 套件的不確定性區間運算與 LPV (Linear Parameter-Varying) 系統檔 `interval.py`。

---

## 1. 區間代數基本運算 (Lines 11 - 60)

區間代數用於在不知道確切參數值的情況下，估算系統輸出的上下界範圍（區間 $[x_{\text{min}}, x_{\text{max}}]$）。

```python
11: def intervals_product(a: Interval, b: Interval) -> np.ndarray:
19:     p = lambda x: np.maximum(x, 0)
20:     n = lambda x: np.maximum(-x, 0)
21:     return np.array(
22:         [np.dot(p(a[0]), p(b[0])) - np.dot(p(a[1]), n(b[0])) - np.dot(n(a[0]), p(b[1])) + np.dot(n(a[1]), n(b[1])),
23:          np.dot(p(a[1]), p(b[1])) - np.dot(p(a[0]), n(b[1])) - np.dot(n(a[1]), p(b[0])) + np.dot(n(a[0]), n(b[0]))])
```
* **區間乘法（Interval Product）**：由於區間中可能包含負數，乘法需要考慮多個正負邊界的組合。這裡使用正部函數 `p` 與負部函數 `n`，實現了向量化且無分支判定（Branchless）的快速矩陣區間乘法，精準推導出乘積的 $[\text{min}, \text{max}]$。

```python
26: def intervals_scaling(a: Interval, b: Interval) -> np.ndarray:
41: def intervals_diff(a: Interval, b: Interval) -> np.ndarray:
```
* `intervals_scaling`：常數矩陣與區間向量的縮放乘積。
* `intervals_diff`：區間減法。計算公式為：$[a_{\text{min}} - b_{\text{max}}, a_{\text{max}} - b_{\text{min}}]$。

---

## 2. 坐標系轉換與路面投影 (Lines 89 - 124)

```python
89: def interval_absolute_to_local(position_i: Interval, lane: AbstractLane) -> Tuple[np.ndarray, np.ndarray]:
97:     position_corners = np.array([[position_i[0, 0], position_i[0, 1]], ...])
101:     corners_local = np.array([lane.local_coordinates(c) for c in position_corners])
102:     longitudinal_i = np.array([min(corners_local[:, 0]), max(corners_local[:, 0])])
103:     lateral_i = np.array([min(corners_local[:, 1]), max(corners_local[:, 1])])
```
* **絕對座標區間轉局部 Frenet 座標區間**：自駕車的安全判定需要在路面局部坐標系中（縱向行駛距離 s、橫向偏離值 d）進行。此函式提取絕對座標的 4 個邊角點，投影到車道 `lane.local_coordinates`，取最值，重新拼裝為縱向與橫向的不確定性區間。

---

## 3. 線性參數時變系統：`LPV` 類別 (Lines 149 - 314)

LPV 用於描述具備不確定性干擾和參數波動的車輛動態方程式：$\dot{x} = A(\theta)x + Bu + D\omega$。

```python
198:     def update_coordinates_frame(self, a0: np.ndarray) -> None:
207:         if not is_metzler(a0):
208:             eig_v, transformation = np.linalg.eig(a0)
209:             if np.isreal(eig_v).all():
211:                 self.coordinates = (transformation, np.linalg.inv(transformation))
```
* **Metzler 矩陣坐標系轉換**：
  * 在不確定性估算中，只有當系統矩陣為 **Metzler 矩陣**（即非對角線元素全部 $\ge 0$）時，區間估算邊界才不會發散，保持單調包容性質。
  * 若當前 $A_0$ 矩陣不滿足條件，此函式對 $A_0$ 進行特徵值分解，建立一個座標變換矩陣，將整個動力學系統投影到 Metzler 坐標系中運行。

```python
295:     def step_interval_predictor(self, x_i: Interval, dt: float) -> np.ndarray:
310:         dx_m = a0 @ x_m - da_p @ n(x_m) - da_n @ p(x_M) + p(d) @ o_m - n(d) @ o_M + b @ u
311:         dx_M = a0 @ x_M + da_p @ p(x_M) + da_n @ n(x_m) + p(d) @ o_M - n(d) @ o_m + b @ u
```
* **區間預測器步進（Interval Predictor Step）**：
  在每個時間步 `dt`，利用 Metzler 矩陣的包容單調性，分別計算狀態下限 $\dot{x}_m$ 的變化量與上限 $\dot{x}_M$ 的變化量，累加實現不確定性安全邊界的實時遞推更新。這在自動駕駛中常用於計算「前方鄰車未來數秒可能行駛的物理包絡範圍（Occupancy Grid）」。
