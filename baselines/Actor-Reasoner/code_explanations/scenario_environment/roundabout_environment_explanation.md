# Actor-Reasoner `scenario_environment/roundabout_environment.py` 逐行詳細代碼解析

本文件解讀 `scenario_environment/` 目錄下用於構建環島車流場景的幾何與路網檔案 `roundabout_environment.py`。

---

## 1. 環島畫布線渲染 (Lines 17 - 45)

```python
17: def scenario_outfit(ax, color=RGB_to_Hex('202,202,202')):
18:     radius = ROUNDABOUT_R - 5
19:     theta = np.linspace(0, 2 * np.pi, 100)
20:     x = radius * np.cos(theta)
21:     y = radius * np.sin(theta)
22:     ax.plot(x, y, c=color)
```
* 利用三角函數 $x = R\cos\theta, y = R\sin\theta$ 在 matplotlib 坐標軸上畫出兩個半徑分別為 15 米與 20 米的同心圓，渲染環島內外車道實線。
* 同時畫出東西南北四個方向的主幹道引導邊界與中心分隔虛線。

---

## 2. 幾何曲線拼接與圓弧插值 (Lines 86 - 237)

環島路徑拼接相較於直線路網複雜得多，主要分成五個物理階段：

```python
227: def concatenate_ref_lane(entrance, exit):
228:     ref_lane1 = entrance_ref_line(entrance, exit)         # 1. 外部主道引道直行線
229:     ref_lane2 = enter_roundabout_ref_line(entrance, exit)  # 2. 右轉進入環島引導過渡線
230:     ref_lane3 = roundabout_ref_line(entrance, exit)        # 3. 環島內部圓弧循跡軌跡
231:     ref_lane4 = exit_roundabout_ref_line(entrance, exit)   # 4. 右轉衝出環島引導過渡線
232:     ref_lane5 = exit_ref_line(entrance, exit)              # 5. 出口直行消散線
```
* **環島內部圓弧插值 (`roundabout_ref_line` - Lines 116-162)**：
  根據入口（南 `s`、東 `e`、北 `n`、西 `w`）到出口的映射，設定不同的極角範圍 $\theta$。
  例如，從南口 `s` 進入、西口 `w` 駛出，需要在環島內行駛大半個圓圈，對應的圓弧極角範圍劃定為：
  `theta = np.linspace(-0.35 * np.pi, 0.85 * np.pi, 6000)`
  利用半徑 $17.5$ 米進行三角函數投影，生成高精度的循跡參考點點陣。

---

## 3. 實時車輛位置重投影與衝突 (Lines 293 - 308)

```python
293: def find_dis2des(entrance, exit, x, y):
294:     ref_line = ALL_REF_LINE[entrance][exit]
295:     gap_list = ALL_GAP_LIST[entrance][exit]
296:     index = np.argmin(np.sqrt((ref_line[:,0] - x)**2 + (ref_line[:,1] - y)**2))
297:     dis2des = gap_list[index]
```
* **位置重投影 (`find_dis2des`)**：
  這是用於外接實車駕駛模擬器或手動操作的工具。給定車輛的 2D 物理座標 `[x, y]`，通過與全局軌跡線 `ref_line` 做歐氏距離最小化搜尋，將其反向投影到 Frenet 座標系中，解出目前車輛距離終點剩餘的弧長 `dis2des`。
* **環島衝突點數據 (Lines 302-307)**：
  在開機時編譯得到 `ALL_REF_LINE` 等快取。
  * `CONFLICT_RELATION`：記載了南口 `s` 和西口 `w` 進入的兩台車，在環島匯流與分流行駛軌跡的預期交會位置（相距起點約 99.7 米處）。
  * `CONFLICT_RELATION_STATE`：衝突點的具體幾何坐標為 `(6.36, -16.60)`。
