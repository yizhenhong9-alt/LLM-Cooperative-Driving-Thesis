# Actor-Reasoner `scenario_environment/merge_environment.py` 逐行詳細代碼解析

本文件解讀 `scenario_environment/` 目錄下用於構建高速公路匯入匝道場景的幾何與路網檔案 `merge_environment.py`。

---

## 1. 繪圖與多項式平滑插值 (Lines 7 - 58)

```python
7: def RGB_to_Hex(rgb):
...
16: def scenario_outfit(ax, color=RGB_to_Hex('202,202,202')):
```
* **畫布邊界渲染**：將 RGB 顏色值轉換成 Hex 十六進制網頁顏色（如將灰色 `202,202,202` 轉換成 `#CACACA`）。並在地圖坐標軸上畫出主線道邊界線（$y = 5$, $y = 0$, $y = 2.5$ 虛線）和匝道斜線。

```python
36: def smooth_ployline(cv_init, point_num=3000):
...
47:     bspl_x = splrep(s_cv, list_x, s=0.1)
48:     bspl_y = splrep(s_cv, list_y, s=0.1)
```
* **B-樣條曲線平滑算法 (B-Spline Smoothing)**：
  自駕車如果沿著折線走，其朝向角與加速度會發生突變跳躍（不符合物理動力學）。
  * 系統接收一組離散的粗糙控制坐標 `cv_init`（如合流折線點）。
  * 計算點與點之間的累積弦長 `s_cv`，將其作為虛擬自變量。
  * 調用 SciPy 的 **`splrep`** 和 **`splev`** 對 X 坐標與 Y 坐標進行 B-樣條三次曲線擬合插值，插值出 3000 個連續平滑點並重新計算弧長 `s_accumulated`，輸出平滑後的平滑路徑。

---

## 2. 合流路網參考線拼接 (Lines 60 - 154)

這部分代碼拼裝了車輛在 Merge 地圖中的全局路徑：

```python
147: def concatenate_ref_lane(entrance, exit):
148:     ref_lane1 = entrance_ref_line(entrance, exit)
149:     ref_lane2 = merging_area_ref_line(entrance, exit)
150:     ref_lane3 = exit_ref_line(entrance, exit)
151:     ref_lane = np.vstack((ref_lane1, ref_lane2))
152:     ref_lane = np.vstack((ref_lane, ref_lane3))
153:     return ref_lane
```
* 將路網分為三個部分：入口引道 `entrance_ref_line`、中段匯入交會區 `merging_area_ref_line`、與出口車道 `exit_ref_line`。
* 呼叫 `np.vstack` 將三段二維陣列坐標沿著縱向拼接，為車輛建立連續可導的全局 Frenet 參考線軌跡。

---

## 3. 世界物理狀態初始化與連通性字典 (Lines 155 - 206)

* **初始速度與距離解碼 (`default_exit_and_state` - Lines 155-179)**：
  隨機生成 $6 \sim 9 m/s$ 的發車速度，根據起點入口確定初始 heading 朝向角，並賦予其 `ori_dis2des`（發車起點到路網出口的累積軌跡米數）。
* **全局參考線表編譯**：
  ```python
  203: ALL_REF_LINE, ALL_GAP_LIST, REF_LINE_TOTAL_LENGTH = record_all_possible_ref_line()
  ```
  在 Python 開機導入本模組時，自動執行 `record_all_possible_ref_line()`。它會計算並緩存所有入口到出口路線的 XY 坐標（`ALL_REF_LINE`）和對應的剩餘距離表（`ALL_GAP_LIST`），防止仿真運算時重複計算插值導致卡頓。
* **物理衝突點字典 (Lines 204-205)**：
  * `CONFLICT_RELATION`：主道 `s` 與匝道 `m` 唯一的衝突交點距離主道發車起點 $97$ 米，距離匝道發車起點 $100$ 米。
  * `CONFLICT_RELATION_STATE`：該衝突點的世界幾何坐標為 `(100, 2.5)`。
