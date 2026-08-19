# Actor-Reasoner `vehicle.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下的車輛屬性管理與初始化模組 `vehicle.py`。

---

## 1. 完整程式碼與逐行解析

```python
1: from sqlalchemy.sql.functions import random
2: import random
3: from params import *
4: import tools
```
* **第 1-4 行**：導入 Python 原生 `random` 模組以及專案全局配置變數 `params`、底層幾何計算工具箱 `tools`。

```python
5: if Scenario_name == 'intersection':
6:     from scenario_environment import intersection_environment as environment
7: elif Scenario_name == 'merge':
8:     from scenario_environment import merge_environment as environment
9: elif Scenario_name == 'roundabout':
10:     from scenario_environment import roundabout_environment as environment
11: else:
12:     raise ValueError('no such environment, check Scenario_name in params')
```
* **第 5-12 行**：**多地圖場景動態環境加載**：
  讀取 `params.py` 中設定的 `Scenario_name`（十字路口、合流區、圓環），動態加載對應的地圖參考線與幾何計算庫為縮寫 `environment`。

```python
15: class Vehicle:
16:     def __init__(self, entrance, exit, aggressiveness, id):
17:         self.id = id
18:         self.entrance = entrance
19:         self.exit = exit
20:         self.aggressiveness = aggressiveness
21:         self.initialize_info()
```
* **第 15-21 行**：定義車輛類別。接收車輛 ID、起點入口 `entrance`、終點出口 `exit` 以及駕駛風格 `aggressiveness`（如 `agg` 激進、`nor` 正常、`con` 保守、或 `cav` 自駕）。呼叫 `initialize_info` 完成物理座標初始化。

```python
23:     def initialize_info(self):
24:         x, y, speed, heading, dis2des, max_speed = environment.default_exit_and_state(self.entrance, self.exit)
25:         self.x = x
26:         self.y = y
27:         self.heading = heading
```
* **第 23-27 行**：調用動態環境函式 `default_exit_and_state`，獲得該路徑的起始 Cartesian 座標 $[x, y]$、初速度、朝向角、該路段總長度 `dis2des`（距離終點的距離）與速限。

```python
28:         if self.entrance == 'm':
29:             random_init_dis2des = 0
30:         else:
31:             random_init_dis2des = random.randint(0, 30)
32:         self.dis2des = dis2des - random_init_dis2des
33:         self.x, self.y = tools.update_pos_from_dis2des_to_Cartesian(self.entrance, self.exit, self.dis2des)
```
* **第 28-33 行**：**隨機車流間距生成**：
  若不是匯入匝道，則隨機扣減 0 到 30 米的 `dis2des`，這可以隨機錯開車輛的發車時間與初始車距。隨後調用 `tools.update_pos_from_dis2des_to_Cartesian` 計算對應的 2D 物理座標，將車輛擺放到正確的路段位置上。

```python
34:         self.speed = speed
35:         self.max_speed = max_speed
36:         self.acc = 0
```
* **第 34-36 行**：設定初速度、最大速度，並將車輛初始物理加速度置為 0，完成初始化。
