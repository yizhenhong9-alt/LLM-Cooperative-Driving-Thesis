# CoDrivingLLM 原始專案 `highway_env/envs/intersection_env.py` 逐行詳細代碼解析

本文件針對 `highway-env` 十字路口模擬環境定義檔 `intersection_env.py` 進行逐行、逐段的功能解析，幫助您理解十字路口幾何路網的構建、車輛優先級路權、多智能體協同獎勵、以及車輛碰撞自動清理機制的實現。

---

## 1. 模組導入與註冊機制 (Lines 1 - 13)

```python
1: from typing import Dict, Tuple
2: 
3: from gym.envs.registration import register
4: import numpy as np
5: 
6: from highway_env import utils
7: from highway_env.envs.common.abstract import AbstractEnv, MultiAgentWrapper
8: from highway_env.road.lane import LineType, StraightLane, CircularLane, AbstractLane
9: from highway_env.road.regulation import RegulatedRoad
10: from highway_env.road.road import RoadNetwork
11: from highway_env.vehicle.kinematics import Vehicle
12: from highway_env.vehicle.controller import ControlledVehicle
```

* **第 8-10 行**：導入建置複雜幾何路口所需的車道元件。`LineType`（虛線/實線）、`StraightLane`（直行車道）、`CircularLane`（圓弧轉彎車道）以及 `RegulatedRoad`（具備優先路權調度的規則路面）。

---

## 2. 環境默認配置：`default_config` (Lines 28 - 69)

```python
28:     @classmethod
29:     def default_config(cls) -> dict:
30:         config = super().default_config()
31:         config.update({
...
46:             "action": {
47:                 "type": "DiscreteMetaAction",
48:                 "longitudinal": True,
49:                 "lateral": False,
50:                 "target_speeds": [0, 4.5, 9]
51:             },
```
* **第 46-51 行**：十字路口的離散動作空間只開放**縱向控制（Longitudinal）**，限制車輛變道。車速目標鎖定在三個離散區間：`[0, 4.5, 9]` m/s（分別對應：靜止/低速通過/高速通過）。

```python
54:             "controlled_vehicles": 1,
55:             "initial_vehicle_count": 10,
56:             "spawn_probability": 0.6,
...
61:             "collision_reward": -5,
62:             "high_speed_reward": 1,
63:             "arrived_reward": 1,
```
* **第 54-56 行**：預設單智能體環境的受控 CAV 為 1 輛，初始生成 10 輛背景車，隨機生成概率為 0.6。
* **第 61-63 行**：十字路口的碰撞懲罰設定為極高的 `-5`（因為路口交匯風險極大），順利通過路口的獎勵（arrived_reward）為 `1`。

---

## 3. 多智能體協同獎勵與自動清理機制 (Lines 71 - 97)

```python
71:     def _reward(self, action: list, obs, env) -> float:
72:         # Cooperative multi-agent reward
73:         return sum(self._agent_reward(action, vehicle) for vehicle in self.controlled_vehicles) \
74:                / len(self.controlled_vehicles)
```
* **第 71-74 行**：計算全體受控 CAV 的**協同均值回報（Cooperative Reward）**。透過將所有自駕車的個體 Reward 求和並平均，促使大模型學會「為了集體效率而主動讓行」的協作精神。

```python
87:     def crashed_and_clean(self):
89:         crashed_agent = False #判定agent是否碰撞
90:         crashed_hv = False  #判定除agent之外的HV是否发生碰撞
91:         for vehicle in self.controlled_vehicles:  #判定：Agent發生碰撞才是真正的碰撞
92:             crashed_agent = crashed_agent or vehicle.crashed
93:         if crashed_agent == False : #agent 没有碰撞
94:             for vehicle in self.road.vehicles:
95:                 if (vehicle not in self.controlled_vehicles) and (vehicle.crashed):  # 选择背景车進行判定
96:                     self.road.vehicles.remove(vehicle)  #  背景車之間如果發生碰撞，直接刪除該背景車
```
* **第 87-97 行**：**【關鍵自定義修改】背景車碰撞自動回收清理**。
  * 系統會檢查是否有自駕車（Agent/CAV）發生碰撞，如果有，該 Episode 標記為碰撞失敗。
  * 若自駕車安全無恙，但**背景人類駕駛車（HV/HDV）之間發生了擦撞，系統會直接呼叫 `remove(vehicle)` 將其從物理世界中抹除**。這是為了防止背景車因模擬器 Bug 自相殘殺而卡死路口（Gridlock），確保自駕車的行車路徑不受背景死鎖的干擾。

---

## 4. 終止判定與步進更新：`_is_terminal`, `step` (Lines 98 - 138)

```python
98:     def _is_terminal(self) -> bool:
99:         self.crashed_and_clean()
100:         return any(vehicle.crashed for vehicle in self.controlled_vehicles) \
101:                or all(self.has_arrived(vehicle) for vehicle in self.controlled_vehicles) \
102:                or self.steps >= self.config["duration"] * self.config["policy_frequency"]-1
```
* **第 98-103 行**：在檢測並清理背景車後，若有任意一台自駕車崩潰、或者所有自駕車均已安全通關抵達終點、或步數超時，則回合終止。

---

## 5. 四路幾何十字路口構建：`_make_road` (Lines 139 - 195)

這段程式碼使用旋轉矩陣和圓弧公式，以數學幾何建置出高精度的無信號燈十字路口：

```python
154:         lane_width = AbstractLane.DEFAULT_WIDTH
155:         right_turn_radius = lane_width + 5  # [m}
156:         left_turn_radius = right_turn_radius + lane_width  # [m}
157:         outer_distance = right_turn_radius + lane_width / 2
158:         access_length = 50 + 50  # [m]
```
* **第 154-158 行**：定義車道寬度（標準約 4 米），右轉半徑為 9 米，左轉半徑為 13 米。十字路口邊界距離中心點 `outer_distance` 約 11 米，接入引道長度為 100 米。

```python
162:         for corner in range(4):
163:             angle = np.radians(90 * corner)
164:             is_horizontal = corner % 2
165:             priority = 3 if is_horizontal else 1
166:             rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
```
* **第 162-166 行**：利用迴圈旋轉四個方向（南、西、北、東，對應 `corner` 0, 1, 2, 3）。水平方向車道設為高路權優先級（`priority = 3`），垂直車道為低路權優先級（`priority = 1`）。定義幾何旋轉矩陣 `rotation`。

```python
167:             # Incoming
170:             net.add_lane("o" + str(corner), "ir" + str(corner),
171:                          StraightLane(start, end, line_types=[s, c], priority=priority, speed_limit=5))
172:             # Right turn
174:             net.add_lane("ir" + str(corner), "il" + str((corner - 1) % 4),
175:                          CircularLane(r_center, right_turn_radius, ...))
177:             # Left turn
179:             net.add_lane("ir" + str(corner), "il" + str((corner + 1) % 4),
180:                          CircularLane(l_center, left_turn_radius, ...))
182:             # Straight
185:             net.add_lane("ir" + str(corner), "il" + str((corner + 2) % 4),
186:                          StraightLane(start, end, ...))
```
* 透過旋轉坐標系，在每個角落依序添加：
  * 引道入口直行車道 `oX -> irX` (Outer to Inner Right)。
  * 右轉圓弧車道 `irX -> il(X-1)`。
  * 左轉圓弧車道 `irX -> il(X+1)`。
  * 直行通過十字路口車道 `irX -> il(X+2)`。
  * 出口直行道 `il(X-1) -> o(X-1)`。

---

## 6. 車輛隨機與預設生成：`_make_vehicles` (Lines 196 - 271)

```python
203:         vehicle_type = utils.class_from_path(self.config["other_vehicles_type"])
204:         vehicle_type.DISTANCE_WANTED = 7  # 降低背景車的期望安全車距，使其開得更緊湊
205:         vehicle_type.COMFORT_ACC_MAX = 6
206:         vehicle_type.COMFORT_ACC_MIN = -3
```
* **第 203-206 行**：設定背景車（IDM）引數。將安全車距縮短至 `7m`（模擬路口擁擠加塞），提升其最大舒適加速度為 6 $m/s^2$。

```python
220:         for ego_id in range(0, self.config["controlled_vehicles"]):
221:             ego_lane = self.road.network.get_lane(("o{}".format(ego_id % 4), "ir{}".format(ego_id % 4), 0))
223:             destination = self.config["destination"] or "o" + str(self.np_random.randint(1, 4))
224:             while destination == "o{}".format(ego_id % 4):
225:                 destination = "o" + str(self.np_random.randint(1, 4))
```
* **第 220-225 行**：在各個入口引道的 60 米處生成自駕車（CAV）。為每台自駕車隨機指派一個**出口目的地**（例如從 0 號南口進入，隨機指派西、北、東口之一為終點），隨後呼叫 `plan_route_to(destination)` 進行路徑導航規劃。

---

## 7. 多智能體擴充環境：`MultiAgentIntersectionEnv` (Lines 289 - 330)

```python
289: class MultiAgentIntersectionEnv(IntersectionEnv):
290:     @classmethod
291:     def default_config(cls) -> dict:
292:         config = super().default_config()
293:         config.update({
294:             "action": {
295:                  "type": "MultiAgentAction",
...
308:             "controlled_vehicles": 4  # here to change to number of CAV
309:         })
```
* **第 289-310 行**：建立繼承自 `IntersectionEnv` 的多智能體版本。
  * 將動作和觀測值封裝為多智能體包裝器 `MultiAgentAction` 與 `MultiAgentObservation`。
  * 設定受控自駕車數量為 **`4`**。這正是 `CoDrivingLLM` 專案中被註冊為 **`intersection-multi-agent-v0`** 的真實環境實體，支持 4 輛自駕車同時進行 V2X 多車談判！
