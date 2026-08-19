# CoDrivingLLM 原始專案 `highway_env/envs/highway_env.py` 逐行詳細代碼解析

本文件針對 `highway-env` 核心模擬環境定義檔 `highway_env.py` 進行逐行、逐段的功能解析，幫助您理解底層物理世界、車輛初始化分佈以及車輛獎懲函數的運作原理。

---

## 1. 模組導入與註冊機制 (Lines 1 - 11)

```python
1: import numpy as np
2: from gym.envs.registration import register
3: 
4: from highway_env import utils
5: from highway_env.envs.common.abstract import AbstractEnv
6: from highway_env.envs.common.action import Action
7: from highway_env.road.road import Road, RoadNetwork
8: from highway_env.utils import near_split
9: from highway_env.vehicle.controller import ControlledVehicle
10: from highway_env.vehicle.kinematics import Vehicle
```

* **第 2 行**：導入 gym 的 `register` 模組，用於將我們自定義的 Python 自駕車類別註冊為 OpenAI Gym 標準環境（使我們可以通過 `gym.make('highway-v0')` 進行實例化）。
* **第 5-6 行**：導入抽象環境基底類別 `AbstractEnv` 以及動作 `Action` 的型態定義。
* **第 7-10 行**：導入路網結構（`Road`, `RoadNetwork`）、受控自駕車控制器 `ControlledVehicle` 以及基本車輛物理學運動 model `Vehicle`。

---

## 2. 環境本體與默認配置：`default_config` (Lines 13 - 57)

```python
13: class HighwayEnv(AbstractEnv):
14:     n_a = 5
15:     n_s = 25
```
* **第 13-15 行**：自定義的 `HighwayEnv` 類別繼承自 `AbstractEnv`。設定離散動作數量為 5（即 `n_a = 5`，對應變道與加減速），狀態特徵維度 `n_s = 25`。

```python
24:     @classmethod
25:     def default_config(cls) -> dict:
26:         config = super().default_config()
27:         config.update({
28:             "observation": {
29:                 "type": "Kinematics",
30:                 "vehicles_count": 15,
31:                 "absolute": True,
32:                 "features": ["presence", "x", "y", "vx", "vy", "cos_h", "sin_h"],
33:             },
```
* **第 28-32 行**：定義**狀態觀測值（Observation）**格式：使用運動學特徵（Kinematics），追蹤包括自車在內周圍最多 15 輛車，抓取絕對物理特徵（座標 x, y，速度 vx, vy，以及朝向角餘弦 cos_h、正弦 sin_h，和是否存在標記 presence）。

```python
33:             "action": {
34:                 "type": "DiscreteMetaAction",
35:             },
36:             "lanes_count": 4,
37:             "screen_width": 1200,
38:             "screen_height": 600,
39:             "centering_position": [0, 0.6],
40:             "scaling": 3,
41:             "vehicles_count": 20,
42:             "controlled_vehicles": 4,  # here to change to number of CAV
43:             "initial_lane_id": None,
44:             "duration": 40,  # [s]
45:             "ego_spacing": 2,
46:             "vehicles_density": 1,
```
* **第 33-35 行**：動作類型為**離散元動作（DiscreteMetaAction）**，即大模型輸出的整數將映射為高階語意：`0: LANE_LEFT`, `1: IDLE`, `2: LANE_RIGHT`, `3: FASTER`, `4: SLOWER`。
* **第 36-41 行**：定義車道數為 4，Pygame 渲染視窗寬 1200 / 高 600，相機縮放比例，以及路段中總車輛數上限為 20 輛。
* **第 42 行**：**`controlled_vehicles`**：設定自駕車（CAV）的數量。CoDrivingLLM 中此參數可以修改為 1 至 4，決定了有多少輛自駕車由大模型接管（剩下的車輛將自動退化為背景車）。
* **第 44-46 行**：設定單回合上限時間為 40 秒，自駕車初始車道分佈的間距（ego_spacing = 2），以及背景車流量密度。

```python
47:             "collision_reward": -1,    # The reward received when colliding with a vehicle.
48:             "right_lane_reward": 0.1,  # The reward received when driving on the right-most lanes, linearly mapped to
49:                                        # zero for other lanes.
50:             "high_speed_reward": 0.4,  # The reward received when driving at full speed, linearly mapped to zero for
51:                                        # lower speeds according to config["reward_speed_range"].
52:             "lane_change_reward": 0,   # The reward received at each lane change action.
53:             "reward_speed_range": [20, 30],
55:             "offroad_terminal": False
56:         })
57:         return config
```
* **第 47-53 行**：設定強化學習權重：碰撞懲罰 `-1`、靠最右側車道獎勵 `0.1`（鼓勵安全駕駛習慣）、高速行駛獎勵 `0.4`。期望的行車速度區間為 20 m/s 到 30 m/s 之間。
* **第 55 行**：若 `offroad_terminal = False`，代表車輛衝出公路邊界時，模擬不會立刻被強制終止。

---

## 3. 路網與車輛實體建立：`_reset`, `_create_road`, `_create_vehicles` (Lines 59 - 89)

```python
59:     def _reset(self, num_CAV=0) -> None:
60:         self._create_road()
61:         self._create_vehicles()
```
* **第 59-61 行**：每次回合重置（reset）時，都會被 Gym 調用。它會清空當前世界，重新呼叫 `_create_road` 與 `_create_vehicles` 重新繪製物理世界。

```python
63:     def _create_road(self) -> None:
64:         """Create a road composed of straight adjacent lanes."""
65:         self.road = Road(network=RoadNetwork.straight_road_network(self.config["lanes_count"]),
66:                          np_random=self.np_random, record_history=self.config["show_trajectories"])
```
* **第 63-66 行**：調用 `RoadNetwork.straight_road_network` 建立包含 4 條相鄰平行直行車道的幾何路網，並綁定隨機數種子。

```python
68:     def _create_vehicles(self) -> None:
69:         """Create some new random vehicles of a given type, and add them on the road."""
70:         other_vehicles_type = utils.class_from_path(self.config["other_vehicles_type"])
71:         other_per_controlled = near_split(self.config["vehicles_count"], num_bins=self.config["controlled_vehicles"])
```
* **第 70-71 行**：讀取背景車（HDV）的類別類型（預設為 IDM 控制型車輛）。調用 `near_split` 函式將總車數（20輛）平均分配給受控自駕車數量（4輛）。這保證了每輛自駕車的周圍都能均勻分佈背景車流。

```python
73:         self.controlled_vehicles = []
74:         for others in other_per_controlled:
75:             vehicle = Vehicle.create_random(
76:                 self.road,
77:                 speed=25,
78:                 lane_id=self.config["initial_lane_id"],
79:                 spacing=self.config["ego_spacing"]
80:             )
81:             vehicle = self.action_type.vehicle_class(self.road, vehicle.position, vehicle.heading, vehicle.speed)
82:             self.controlled_vehicles.append(vehicle)
83:             self.road.vehicles.append(vehicle)
```
* **第 73-83 行**：在迴圈中隨機初始化每一輛**自駕車（CAV）**。設定初速為 25 m/s，並通過 `action_type.vehicle_class` 將車輛包裝為可由離散動作控制的實體，存入 `self.controlled_vehicles` 中並加入物理道路。

```python
85:             for _ in range(others):
86:                 vehicle = other_vehicles_type.create_random(self.road, spacing=1 / self.config["vehicles_density"])
87:                 vehicle.randomize_behavior()
88:                 self.road.vehicles.append(vehicle)
```
* **第 85-88 行**：在每輛 CAV 之間，隨機建立 `others` 數量的背景車（HDV），調用 `randomize_behavior` 隨機化他們的 IDM 期望車速與MOBIL 變道庫閾值，模擬千奇百怪的真實人類駕駛行為，並加入道路。

---

## 4. 運動獎懲函數設計：`_reward` (Lines 90 - 111)

```python
90:     def _reward(self, action: Action, obs, env) -> float:
96:         neighbours = self.road.network.all_side_lanes(self.vehicle.lane_index)
97:         lane = self.vehicle.target_lane_index[2] if isinstance(self.vehicle, ControlledVehicle) \
98:             else self.vehicle.lane_index[2]
```
* **第 96-98 行**：獲取自車當前行駛的車道編號（`lane`），以及總車道數（`neighbours`）。

```python
100:         forward_speed = self.vehicle.speed * np.cos(self.vehicle.heading)
101:         scaled_speed = utils.lmap(forward_speed, self.config["reward_speed_range"], [0, 1])
102:         reward = \
103:             + self.config["collision_reward"] * self.vehicle.crashed \
104:             + self.config["right_lane_reward"] * lane / max(len(neighbours) - 1, 1) \
105:             + self.config["high_speed_reward"] * np.clip(scaled_speed, 0, 1)
```
* **第 100-101 行**：計算指向車道正前方的速度分量 `forward_speed`。調用 `utils.lmap` 進行線性映射：當車速落入 `[20, 30]m/s` 區間時，其速度評分被對應縮放至 `[0, 1]` 區間。
* **第 102-105 行**：**計算複合 Reward 值**：
  $$\text{Reward} = (-1 \times \text{是否碰撞}) + (0.1 \times \text{靠右車道比例}) + (0.4 \times \text{速度評分})$$

```python
106:         reward = utils.lmap(reward,
107:                           [self.config["collision_reward"],
108:                            self.config["high_speed_reward"] + self.config["right_lane_reward"]],
109:                           [0, 1])
110:         reward = 0 if not self.vehicle.on_road else reward
111:         return reward
```
* **第 106-111 行**：將剛才得到的總獎勵值進行歸一化，映射到 `[0, 1]` 區間內。如果車輛開出馬路邊界（`not self.vehicle.on_road`），則強行將獎勵清零。

---

## 5. 終止條件與快速變體：`HighwayEnvFast` (Lines 113 - 160)

```python
113:     def _is_terminal(self) -> bool:
114:         """The episode is over if the ego vehicle crashed or the time is out."""
115:         return self.vehicle.crashed or \
116:             self.steps >= self.config["duration"] or \
117:             (self.config["offroad_terminal"] and not self.vehicle.on_road)
```
* **第 113-117 行**：當以下任一條件成立，回合結束：車輛撞毀（`self.vehicle.crashed`）、運行步數超出了限制時間（40秒）、或開啟衝出公路終止且車輛開出馬路。

```python
124: class HighwayEnvFast(HighwayEnv):
```
* **第 124-149 行**：定義了一個**加速運行版本 `HighwayEnvFast`**：
  * 將模擬頻率降為 5Hz（開銷小），車道數降為 3，回合長度降為 30 秒。
  * **關鍵優化**：第 146-148 行遍歷所有背景車，將他們的 `check_collisions` 設為 `False`。即**不計算背景車與背景車之間的碰撞**，僅計算自駕車（CAV）與環境車的碰撞，這大幅省去了 80% 的物理重疊檢測計算量，使得模擬運算速度翻倍。

```python
151: register(
152:     id='highway-v0',
153:     entry_point='highway_env.envs:HighwayEnv',
154: )
```
* **第 151-160 行**：向 Gym 架構正式註冊 `highway-v0` 與 `highway-fast-v0` 兩個環境 ID，對應其各自的類別路徑。
