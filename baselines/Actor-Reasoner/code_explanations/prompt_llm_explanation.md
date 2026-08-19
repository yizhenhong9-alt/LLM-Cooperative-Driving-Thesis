# Actor-Reasoner `prompt_llm.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下用於生成決策 Prompt 的模組檔 `prompt_llm.py`。它負責對模擬器提取的車輛狀態進行文字包裝，並提供微觀物理规则檢驗。

---

## 1. 系統提示詞範本定義：`PRE_DEF_PROMPT` (Lines 12 - 58)

```python
18:         self.SYSTEM_MESSAGE_PREFIX = """You are now act as a autonomous vehicle motion planner, who generate safe decision. 
19:     Except for generate decision, to improve safety, you should also share your intention to express what you going to do to your surrounding vehicle. 
20:     Now you are driving at an intersection."""
```
* **角色與意圖共享設定**：大模型被指派為運動規劃器（motion planner），指令中特別強調了：*「除了決策外，為了提升安全，你還必須向周圍車輛主動共享你的行車意圖（share your intention）」*。

---

## 2. 物理規則安全盾 (Lines 96 - 179)

與 CoDrivingLLM 類似，定義了多個微觀安全判定類別，為大模型提供底層物理約束文本：

### A. 加速安全判定：`isAccelerationConflictWithCar` (Lines 96-118)
* 假設自車以 $3.0 m/s^2$ 舒適加速度前進，計算與前車的 TTC 時間。如果 $TTC < 5$ 秒，安全盾直接發出紅色警告：
  `"acceleration will cause serious danger, must slower your speed."`

### B. 維持車速與減速安全判定 (Lines 120-179)
* `isKeepSpeedConflictWithCar`：校驗在當前車道維持現有速度，是否會與前車或後車發生物理衝突。
* `isDecelerationSafe`：檢測如果重踩煞車減速（$-6.0 m/s^2$），後車是否有足夠的安全追尾時距。如果距離太近，會提示大模型：
  `"deceleration with current speed may be conflict with VehX, you should maintain speed or accelerate."`

---

## 3. 衝突幾何場景文字化：`interaction_vehicle` (Lines 189 - 204)

```python
189: def interaction_vehicle(ego_info, other_info):
190:     ego_direction = 'going straight' if environment.if_going_straight(ego_info.entrance, ego_info.exit) else 'turning'
...
197:         msg += f'Your surrounding vehicle is now {other_info_direction}, its ACTUAL last action is {other_info_action}, ' \
198:                f'the position of conflict point ... is ({...}). ' \
199:                f'his speed is {round(other_info.speed, 1)}, distance to conflict point is {round(tools.get_dis2cp(other_info, ego_info), 1)}. ' \
```
* **交會狀態即時序列化**：
  * 解析自車是直行（going straight）還是轉彎（turning）。
  * 提取衝突點在世界座標系中的座標。
  * 計算並輸出兩車各自的時速、以及各自距離衝突交點（Conflict Point）的直線距離（meters）。這為大模型推斷路權提供了極高精度的邊界資訊。
