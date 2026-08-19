# CoDrivingLLM `highway_env/utils.py` 逐行詳細代碼解析

本文件解讀 `highway_env` 套件的基礎數學工具與幾何碰撞檢測算法檔 `utils.py`。

---

## 1. 核心實用工具函式 (Lines 1 - 57)

```python
11: def do_every(duration: float, timer: float) -> bool:
12:     return duration < timer
```
* 判定當前累計計時 `timer` 是否大於指定的周期時間 `duration`，用於定時執行任務（如每過 1 秒執行一次大腦決策）。

```python
15: def lmap(v: float, x: Interval, y: Interval) -> float:
16:     """Linear map of value v with range x to desired range y."""
17:     return y[0] + (v - x[0]) * (y[1] - y[0]) / (x[1] - x[0])
```
* **線性映射（Linear Map）**：將數值 `v` 從原始區間 `x` 等比例映射到期望目標區間 `y`。在仿真中常用於將車速或車道編號轉換為 `[0, 1]` 區間的強化學習 Reward 值。

```python
20: def class_from_path(path: str) -> Callable:
21:     module_name, class_name = path.rsplit(".", 1)
22:     class_object = getattr(importlib.import_module(module_name), class_name)
23:     return class_object
```
* **動態加載類別（Dynamic Class Loading）**：根據字串路徑（例如 `"highway_env.vehicle.behavior.IDMVehicle"`）利用 `importlib` 在執行期動態加載並回傳該類別物件，實現模組解耦。

```python
25: def near_split(x, num_bins=None, size_bins=None):
...
36:     if num_bins:
37:         quotient, remainder = divmod(x, num_bins)
38:         return [quotient + 1] * remainder + [quotient] * (num_bins - remainder)
```
* **接近均等切分（Near-Even Split）**：將一個總數 `x` 平分到 `num_bins` 個箱子中。若無法整除，餘數將自動遞增分配給前幾個箱子（例如將 20 輛背景車分配給 4 輛 CAV，會回傳 `[5, 5, 5, 5]`）。

```python
46: def not_zero(x: float, eps: float = 1e-2) -> float:
55: def wrap_to_pi(x: float) -> float:
```
* `not_zero`：防止除以零的安全防護，若數值小於 eps，則強行以正負 eps 代替。
* `wrap_to_pi`：將角度轉換並限制在弧度 $[-\pi, \pi]$ 的範圍內，避免轉向控制時數值溢出。

---

## 2. 幾何碰撞與旋轉矩陣運算 (Lines 59 - 138)

此部分代碼用於在二維物理世界中檢測車身（旋轉矩形）是否與周圍車身發生碰撞。

```python
70: def point_in_rotated_rectangle(point: np.ndarray, center: np.ndarray, length: float, width: float, angle: float) \
71:         -> bool:
82:     c, s = np.cos(angle), np.sin(angle)
83:     r = np.array([[c, -s], [s, c]])
84:     ru = r.dot(point - center)
85:     return point_in_rectangle(ru, (-length/2, -width/2), (length/2, width/2))
```
* **判定點是否在旋轉矩形內部**：將目標點減去矩形中心，乘以旋轉矩形的反向旋轉矩陣 `r`，將座標變換回未旋轉的局部座標系中，最後直接呼叫 `point_in_rectangle` 進行簡單的邊界框判定。

```python
105: def rotated_rectangles_intersect(rect1: Tuple[Vector, float, float, float],
106:                                  rect2: Tuple[Vector, float, float, float]) -> bool:
114:     return has_corner_inside(rect1, rect2) or has_corner_inside(rect2, rect1)
```
* **兩個旋轉矩形（車身）是否相交（碰撞）**：利用 `has_corner_inside`，檢查第一個矩形的 4 個頂點是否落入第二個矩形內部，或第二個矩形的頂點落入第一個之中。若是，即判定兩車相撞。

---

## 3. 信賴區間估算與多胞形計算 (Lines 139 - 223)

這部分代碼為高級預測模組，用於動態估算系統參數（$\theta$）的邊界信賴橢圓（Confidence Ellipsoid）。

```python
139: def confidence_ellipsoid(data: Dict[str, np.ndarray], lambda_: float = 1e-5, delta: float = 0.1, sigma: float = 0.1,
140:                          param_bound: float = 1.0) -> Tuple[np.ndarray, np.ndarray, float]:
153:     g_n_lambda = 1/sigma * np.transpose(phi) @ phi + lambda_ * np.identity(phi.shape[-1])
154:     theta_n_lambda = np.linalg.inv(g_n_lambda) @ np.transpose(phi) @ y / sigma
```
* **信賴橢圓（Confidence Ellipsoid）**：利用正則化最小二乘法（RLS），對觀測特徵矩陣 `phi` 和輸出 `y` 計算葛拉姆矩陣 `g_n_lambda` 及其逆矩陣，推導出當前物理參數的最優估計值 $\theta_n$ 和信賴橢圓半徑 $\beta_n$。

```python
161: def confidence_polytope(data: dict, parameter_box: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
172:     values, pp = np.linalg.eig(g_n_lambda)
173:     radius_matrix = np.sqrt(beta_n) * np.linalg.inv(pp) @ np.diag(np.sqrt(1 / values))
```
* **信賴多胞形（Confidence Polytope）**：對葛拉姆矩陣進行特徵值分解（`np.linalg.eig`），將信賴橢圓映射並逼近為一個緊湊的多胞形邊界頂點集合，常用於自適應自駕控制中的魯棒安全約束計算。
