# Actor-Reasoner `scenario_environment/intersection_environment.py` 逐行詳細代碼解析

本文件解讀 `scenario_environment/` 目錄下最具挑戰的城市無信號十字路口場景路網檔案 `intersection_environment.py`。由於十字路口包含東西南北 8 個入口與大量轉彎分支，其幾何數據和衝突拓撲點的排列組合極為龐大。

---

## 1. 轉彎方向語意判定 (Lines 65 - 93)

```python
65: def if_right_turning(entrance, exit):
66:     if entrance == 'w2' and exit == 's2': return True
...
77: def if_left_turning(entrance, exit):
78:     if entrance == 'w1' and (exit == 'n1' or exit == 'n2'): return True
```
* **轉彎判定**：通過靜態比對起終點的節點元組，判定該車是在執行「右轉」、「左轉」還是「直行」。
  **作用**：此判定字串直接發送給大模型決策 Prompt（如：`"Your are now turning"`），並決定博弈效用計算中使用的不同權重（如右轉彎在博弈時享有不同的側向跟蹤懲罰）。

---

## 2. 8 入口複雜路口軌跡擬合 (Lines 95 - 280)

```python
95: def intersection_ref_line(entrance, exit):
98:     if entrance == 'n2' and exit == 'w2':
99:         cv_init = np.array([[-7.5, 15], [-7.5, 13], [-9.5, 9.5], [-13, 7.5], [-15, 7.5]])
```
* **控制折線定義**：
  針對路口內所有的流向（直行、左轉、右轉），人工標記了最優的二次/三次過渡折線控制點。
  例如，從北口右轉車道 `n2` 右轉至西出口 `w2`，其控制點序列包含 $[[-7.5, 15], \dots, [-15, 7.5]]$，涵蓋了減速切入、弧頂與切出。
* **樣條曲線平滑（smooth_polyline）**：同樣將這些折線送入三次 B-Spline 插值器擬合出 3000 個高精度的連續路徑點。

---

## 3. 全局連通性與三段路網拼接 (Lines 282 - 338)

```python
298: def concatenate_ref_lane(entrance, exit):
299:     ref_lane1 = entrance_ref_line(entrance, exit)
300:     ref_lane2 = intersection_ref_line(entrance, exit)
301:     ref_lane3 = exit_ref_line(entrance, exit)
```
* 將城市路網劃分為路口外直行引道、路口內交會軌跡、以及出路口消散車道，執行垂直拼接。
* **動態連通性編譯**：
  在開機加載本模組時，對 `params.py` 中宣告的 8 個入口 `INTERSECTION_POSSIBLE_ENTRANCE` 與連通關係字典進行遍歷，自動生成並緩存所有流向的軌跡參考線與剩餘距離對照表。

---

## 4. 全局衝突字典矩陣（CONFLICT_RELATION / STATE - Lines 335 - 338）

由於 8 個入口流向極多，其幾何交會衝突點的數量極其龐大。本檔以一個巨型嵌套字典靜態保存了所有可能發生軌跡交叉的「兩車起終點組合」：
* **`CONFLICT_RELATION`**：
  例如，`CONFLICT_RELATION['n2']['s2']['s1n1'] = 70` 記載了自北向南直行的車輛（`n2` -> `s2`），與自南向北直行的車輛（`s1` -> `n1`），在距離北發車起點 $70$ 米處會發生碰撞軌跡交疊。
* **`CONFLICT_RELATION_STATE`**：
  標記了該具體衝突點的世界 XY 坐標（如 `(2.5, 2.5)` 座標點）。這被 tools 模組直接讀取，計算兩車距該點的相對距離，並做為語意 Prompt 包裝發送給大模型進行路權博弈談判。
