# CoDrivingLLM 原始專案 `highway_env/envs/merge_env_v1.py` 逐行詳細代碼解析

本文件針對 `highway-env` 匝道匯入模擬環境定義檔 `merge_env_v1.py` 進行逐行、逐段的功能解析，幫助您理解匯入區（Merge）的幾何路網設計、正弦車道（SineLane）拼接、首時差安全懲罰（Headway Cost）以及車輛避讓機制。

---

## 1. 模組導入與環境註冊 (Lines 1 - 15)

```python
1: from gym.envs.registration import register
...
5: from highway_env.road.lane import LineType, StraightLane, SineLane
...
7: from highway_env.vehicle.controller import ControlledVehicle, MDPVehicle
...
12: from .merge_env import *
```

* **第 5 行**：導入 `SineLane`（正弦曲線車道）。這是為合流匝道的過渡段設計的，用於產生平滑的Ｓ型變道曲線。
* **第 12 行**：導入同目錄下的 `merge_env.py`，使本環境可以直接使用 `Scenario`、`Vehicle` 數據類別進行 JSON 數據序列化。

---

## 2. 默認參數配置與自定義 Reward：`_agent_reward` (Lines 28 - 120)

```python
28:     @classmethod
29:     def default_config(cls) -> dict:
...
46:             "COLLISION_REWARD": 30,  # default=200
47:             "HIGH_SPEED_REWARD": 1,  # default=0.5
48:             "HEADWAY_COST": 4,  # default=1
49:             "HEADWAY_TIME": 1.2,  # default=1.2[s]
50:             "MERGING_LANE_COST": 4,  # default=4
```
* **第 46-50 行**：定義合流區的特殊懲罰項。`COLLISION_REWARD = 30` 代表碰撞扣分值，`MERGING_LANE_COST = 4` 代表滯留在匝道上的時間處罰。**`HEADWAY_TIME = 1.2`** 規定車輛的最小期望安全車頭時距（Time Headway）為 1.2 秒。

```python
74:         if vehicle.lane_index == ("b", "c", 1):
75:             Merging_lane_cost = - np.exp(-(vehicle.position[0] - sum(self.ends[:3])) ** 2 / (
76:                     10 * self.ends[2]))
```
* **第 74-76 行**：**計算滯留匝道處罰（Merging Lane Cost）**：
  如果車子一直卡在匯入匝道 `("b", "c", 1)` 內不併入主線，系統會根據其當前 X 座標計算出一個指數衰減的 Cost。車輛越接近匝道終點卻仍未變道，此處罰會呈指數級暴增，強迫大模型儘快做出變道決策。

```python
80:         # compute headway cost
81:         headway_distance = 15 # default: 12
82:         headway_cost = 0
83:         for other in road.vehicles:
84:             if other is not vehicle and np.linalg.norm(other.position - vehicle.position) < headway_distance:
85:                 headway_cost -= 1
```
* **第 80-85 行**：**車頭時距安全懲罰（Headway Cost）**：
  遍歷周圍其它的車輛。一旦發現任何鄰車與自駕車的物理距離小於 15 公尺，`headway_cost` 就會累加懲罰值。這能訓練大模型保持行車間距，避免尾隨前車太近（Tailgating）。

---

## 3. 合流路網幾何構建：`_make_road` (Lines 139 - 223)

這段程式碼以數學幾何拼接出包含主線道與匯入匝道的合流區路網：

```python
155:         net = RoadNetwork()
156:         n, c, s = LineType.NONE, LineType.CONTINUOUS, LineType.STRIPED
157:         c_s = [c, s]
```
* **第 156-157 行**：定義車道線類型（無車道線 `NONE`、實線 `CONTINUOUS`、虛線 `STRIPED`）。

```python
159:         # Highway lanes
160:         for i in range(cls.lanes_count()):
161:             net.add_lane("a", "b", StraightLane(np.array([0, i * 4]), np.array([sum(cls.ends[:1]), i * 4]), line_types=c_s, speed_limit=30))
162:             net.add_lane("b", "c", StraightLane(np.array([sum(cls.ends[:1]), i * 4]), np.array([sum(cls.ends[:2]), i * 4]), line_types=c_s, speed_limit=30))
163:             net.add_lane("c", "d", StraightLane(np.array([sum(cls.ends[:2]), i * 4]), np.array([sum(cls.ends[:3]), i * 4]), line_types=c_s, speed_limit=30))
```
* **第 159-163 行**：建置高速公路主線道（Lane 0）。將主線劃分為 a、b、c、d 四個區域，由長度分別為 80米、80米、80米、80米的 straight_lanes 順次拼接而成。

```python
165:         # Merging lane
166:         # Access ramp
167:         amplitude = 3.25
168:         ljk = StraightLane(np.array([0, 12 + amplitude]), np.array([cls.ends[0], 12 + amplitude]), line_types=[c, c], forbidden=True, speed_limit=30)
```
* **第 167-168 行**：建置匯入引道（Access Ramp）。Y 軸設在偏離主線的 12+3.25 = 15.25 米處，長度為 80 米。

```python
169:         # Sine merge
170:         lkb = SineLane(ljk.position(cls.ends[0], 0), np.array([sum(cls.ends[:2]), 4]), amplitude, -np.pi / 2, line_types=[c, c], forbidden=True, speed_limit=30)
```
* **第 170-171 行**：**正弦過渡車道（SineLane）**：
  這是匯入區的點睛之筆。它使用正弦波形曲線，將引道的終點 `ljk.position` 平滑地連接到主線道的合流起點 `np.array([sum(cls.ends[:2]), 4])`（Y 軸從 15.25 米平滑過度至 4 米）。這提供了極其逼真的彎道合流物理軌跡。

---

## 4. 車輛生成與多智能體包裝：`_make_vehicles`, `MultiAgentMergeEnv` (Lines 224 - 344)

```python
233:         # Controlled vehicles
234:         self.controlled_vehicles = []
235:         for ego_id in range(0, self.config["controlled_vehicles"]):
236:             ego_vehicle = self.action_type.vehicle_class(
237:                 self.road,
238:                 self.road.network.get_lane(("a", "b", 0)).position(30 + 10 * ego_id, 0),
239:                 speed=30)
240:             self.road.vehicles.append(ego_vehicle)
241:             self.controlled_vehicles.append(ego_vehicle)
```
* **第 235-241 行**：在主線道（a區到b區）隨機間距生成受控自駕車（CAV），設定行車速限為 30 m/s。

```python
290: class MultiAgentMergeEnv(MergeEnv):
```
* **第 290-311 行**：定義多智能體匯入環境類別，重寫動作與狀態為 `MultiAgentAction` 與 `MultiAgentObservation`，這對應了 `CoDrivingLLM` 用於測試匯入場景的 Gym 實體。
