# CoDrivingLLM `highway_env/envs/common/action.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下的動作定義與執行器映射檔 `action.py`。

---

## 1. 動作基底類別：`ActionType` (Lines 16 - 58)

```python
16: class ActionType(object):
19:     def __init__(self, env: 'AbstractEnv', **kwargs) -> None:
20:         self.env = env
21:         self.__controlled_vehicle = None
```
* **作用**：定義所有控制動作的抽象基底類別。每個動作類型都與當前環境 `env` 綁定，並持有一個指向受控車輛的私有變數 `__controlled_vehicle`。

---

## 2. 連續動作空間控制：`ContinuousAction` (Lines 60 - 133)

```python
60: class ContinuousAction(ActionType):
69:     ACCELERATION_RANGE = (-5, 5.0)  # 加速度邊界
72:     STEERING_RANGE = (-np.pi / 4, np.pi / 4)  # 轉向角邊界（正負45度）
```
* **空間定義 (Lines 106-108)**：返回一個數值介於 `[-1, 1]` 之間的 Gym Box 空間。如果同時啟動縱橫向控制，則輸出形狀為 `(2,)` 的 NumPy 陣列 `[加速度, 轉向角]`。
* **物理執行 (Lines 114-132)**：
  * 當調用 `act(action)` 時，首先限制輸入介於 `[-1, 1]`。
  * 調用 `utils.lmap` 函數，將 `[-1, 1]` 比例等比映射回真實的物理量（如將 `1` 映射為最大加速度 `5.0 m/s²`，將 `-1` 映射為最急煞車 `-5.0 m/s²`）。
  * 調用 `self.controlled_vehicle.act(...)` 將物理指令注入底層車輛動力學模型中。

---

## 3. 離散宏動作空間控制：`DiscreteMetaAction` (Lines 135 - 223)

這是大模型自駕專案中**最核心被調用的動作控制模組**：

```python
135: class DiscreteMetaAction(ActionType):
140:     ACTIONS_ALL = {
141:         0: 'LANE_LEFT',
142:         1: 'IDLE',
143:         2: 'LANE_RIGHT',
144:         3: 'FASTER',
145:         4: 'SLOWER'
146:     }
```
* **初始化 (Lines 164-187)**：
  * 根據環境設定，過濾並加載可用的離散動作。例如在直行高速路中同時支持變道與加減速（`ACTIONS_ALL`）；在十字路口只啟用縱向跟車（`ACTIONS_LONGI`，即限制左右變道）。
* **物理執行 (Lines 217-222)**：
  * 接收整數動作 ID（如 `3`）。
  * 從 `ACTIONS_ALL` 中匹配出對應的文字動作名稱（`'FASTER'`）。
  * 呼叫 **`self.controlled_vehicle.act('FASTER')`**。此車輛實體是 `MDPVehicle`，它會根據 `'FASTER'` 自動調整 IDM 的目標速度，實現智能加減速。

---

## 4. 多智能體動作包裝器：`MultiAgentAction` (Lines 225 - 262)

```python
225: class MultiAgentAction(ActionType):
226:     def __init__(self, env: 'AbstractEnv', action_config: dict, **kwargs) -> None:
...
233:         for vehicle in self.env.controlled_vehicles:
234:             action_type = action_factory(self.env, self.action_config)
235:             action_type.controlled_vehicle = vehicle
236:             self.agents_action_types.append(action_type)
```
* **多車解析 (Lines 245-250)**：
  * 接收一個元組動作（如 `(3, 1, 4, 3)`，代表 4 輛自駕車的決策）。
  * 遍歷全體受控自駕車列表 `self.agents_action_types`，將第 $i$ 個動作分派給第 $i$ 輛車獨立調用 `action_type.act()`。這支援了多車 V2X 的協同前進。
* **工廠模式 (Lines 253-262)**：
  * `action_factory()` 負責根據 config 配置檔中的 `"type"`（`ContinuousAction` / `DiscreteMetaAction` / `MultiAgentAction`），自動初始化對應的動作類別物件並回傳。
