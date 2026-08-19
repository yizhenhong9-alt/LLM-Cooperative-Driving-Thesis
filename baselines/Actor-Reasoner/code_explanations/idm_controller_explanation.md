# Actor-Reasoner `idm_controller.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下用於微觀跟車煞停的控制器 `idm_controller.py`。

---

## 1. 衝突點距離更新與 Yielding 讓行設定 (Lines 15 - 43)

```python
15: class IDM:
16:     def __init__(self, ego_info, other_info, llm_action):
17:         self.ego_info = ego_info
18:         self.idm_parameter = [
19:             2,  # 靜止安全間距 (m)
20:             2,  # 期望安全車頭時距 (s)
21:             2,  # 最大舒適加速度 (m/s^2)
...
24:             -4, # 最大緊急減速度 (m/s^2)
25:         ]
```
* **初始化 (Lines 15-30)**：
  綁定自車與對手車的屬性。設定經典 IDM 的車頭時距（2 秒）、最大舒適加速度（$2 m/s^2$）與緊急煞車（$-4 m/s^2$）。

```python
32:     def update_d(self):
33:         if str(self.other_info.entrance) + str(self.other_info.exit) in environment.CONFLICT_RELATION[self.ego_info.entrance][self.ego_info.exit]:
34:             ego_dis2cp = self.ego_info.dis2des - environment.CONFLICT_RELATION[self.ego_info.entrance][self.ego_info.exit][str(self.other_info.entrance) + str(self.other_info.exit)]
35:             other_dis2cp = self.other_info.dis2des - environment.CONFLICT_RELATION[self.ego_info.entrance][self.ego_info.exit][str(self.ego_info.entrance) + str(self.ego_info.exit)]
36:             if ego_dis2cp > 0 and other_dis2cp > 0:
37:                 distance = ego_dis2cp - other_dis2cp - 3 * VEH_L - MIN_STOP_GAP
```
* **衝突相對距離計算 (Lines 32-43)**：
  * **路徑交會判定**：檢測對手車起終點路徑與自駕車是否在 `CONFLICT_RELATION` 拓撲字典中存在交點。
  * **相對距離計算**：
    * `ego_dis2cp`：自車距衝突點（Conflict Point）的剩餘距離。
    * `other_dis2cp`：對手車距衝突點的剩餘距離。
  * 若兩車均未通過交會點（均大於 0），則相對跟車距離被設置為：
    $$\text{distance} = \text{ego\_dis2cp} - \text{other\_dis2cp} - 3 \cdot \text{VEH\_L} - \text{MIN\_STOP\_GAP}$$
    這將「前車與後車在兩條交會道上的相對幾何間距」虛擬轉化為了「同一條直道上的跟車距離」，方便統一套用 IDM 公式進行防追尾計算。

---

## 2. 大模型宏指令翻譯輸出 (Lines 50 - 74)

```python
50:     def cal_acceleration(self):
...
57:         if self.llm_action == 'FASTER':
58:             acc = self.idm_parameter[2]
59:         elif self.llm_action == 'IDLE':
60:             acc = 0
61:         elif self.llm_action == 'SLOWER':
62:             acc = self.idm_parameter[5]
```
* **控制指令轉換 (Lines 50-74)**：
  微觀控制器接收來自 Actor 快速檢索得到或 Reasoner 推理得到的宏動作 `llm_action`：
  * **`'FASTER'`**：將加速度直接設為最大舒適值 $2.0 m/s^2$，車輛全力前進。
  * **`'IDLE'`**：加速度直接歸零，車輛維持現狀前進。
  * **`'SLOWER'`**：將加速度設為大減速值 $-4.0 m/s^2$（緊急煞車），車輛全力減速避讓。
  * 若出現非法文字，預設退化為 `'SLOWER'`，確保行車安全第一。
