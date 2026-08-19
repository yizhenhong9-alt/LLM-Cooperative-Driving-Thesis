# Actor-Reasoner `tools.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下底層物理模擬幾何計算工具箱 `tools.py`。它負責為輕量模擬器提供運動學狀態演化、TTC 物理公式求解以及 Matplotlib 圖形可視化。

---

## 1. 衝突時間（TTCP）幾何公式求解：`cal_ttcp` (Lines 50 - 75)

這是預測車輛抵達衝突交點所需秒數（Time-To-Conflict-Point）的核心物理公式：

```python
50: def cal_ttcp(speed_limit, veh_dis2cp, veh_v, veh_acc):
51:     if veh_acc > 0:
52:         t_acc2max = (speed_limit - veh_v) / veh_acc
53:         dis_acc2max = veh_v * t_acc2max + 0.5 * veh_acc * t_acc2max ** 2
```
* **加速階段判定 (Lines 51-59)**：
  * 當車子有正加速度時，先計算其加速到地圖速限 `speed_limit` 所需時間 `t_acc2max` 以及此期間行進的距離 `dis_acc2max`。
  * **未達速限**：若距離小於距衝突點的距離 `veh_dis2cp`，說明在抵達衝突點前車速已飽和。總時間為加速時間加上後續以最高限速勻速行駛的剩餘時間。
  * **加速抵達**：若在加速過程中就已抵達衝突點，則解一元二次方程求得抵達秒數：
    $$v_{\text{cp}} = \sqrt{v_0^2 + 2 a \cdot d_{\text{cp}}}$$
    $$t_{\text{cp}} = \frac{v_{\text{cp}} - v_0}{a}$$

```python
60:     elif veh_acc < 0:
61:         dis_acc2stop = veh_v ** 2 / (2 * abs(veh_acc))
62:         if dis_acc2stop < veh_dis2cp:
63:             ttcp = 10000
```
* **減速煞停判定 (Lines 60-66)**：
  * 若車輛在減速中，先計算其減速到 0 煞停所需的制動距離 `dis_acc2stop`。
  * **提前煞停**：若制動距離小於距衝突點的距離，說明車輛會在抵達衝突點之前就已經安全停下。此時將 TTCP 設為一個代表無窮大的虛擬安全值 `10000` 秒（代表絕不會在衝突點發生相撞）。
  * **滑行抵達**：若制動距離大於衝突點距離，說明車輛會滑行穿過衝突點，套用公式解出抵達秒數。
* **勻速抵達 (Lines 67-71)**：
  若加速度為 0，則直接用距離除以車速：`ttcp = dis2cp / v`。若車速為 0 且未達衝突點，則返回 `10000`。

---

## 2. 經驗 Key 生成器：`scenario_experience_generator` (Lines 230 - 260)

```python
258:     sce_descrip = f'Conflict info: instruction is {instruction}, disdes is {ego_info.dis2des}, delta_ttcp is {delta_ttcp}, delta_disdes is {delta_dis2des}, delta_v is {delta_speed}; ' \
259:                   f'Interaction vehicle driving style: {driving_style}; Interaction vehicle intention: {llm_output[2]}; HMI info: {llm_output[1]}; Human instruction: {human_instruction}.'
```
* **語意特徵拼接**：
  計算兩車的 $\Delta TTCP$、速差、距離差，將其離散化並拼接為固定的字串範本。
  **作用**：此字串會作為 ChromaDB 的 `page_content` 寫入。在 Actor 快速檢索時，當前狀態也會被此函數轉化為相同的字串格式進行語意比對。

---

## 3. Frenet 坐標向 Cartesian 二維座標變換 (Lines 262 - 268)

```python
262: def update_pos_from_dis2des_to_Cartesian(entrance, exit, dis2des):
263:     ref_line = environment.ALL_REF_LINE[entrance][exit]
265:     index = np.argmin(abs(gap_list - dis2des))
266:     x = ref_line[index, 0]
```
* 模擬器內部使用一維的 `dis2des`（距離終點的剩餘米數）進行物理積分遞推。
* 本函式讀取對應地圖路段的幾何參考線點陣 `ALL_REF_LINE`，通過尋找最接近剩餘米數的點索引，將其映射轉換為二維平面上的真實 `[x, y]` 座標以供動態繪圖與碰撞判斷。
