# CoDrivingLLM `highway_env/road/objects.py` 逐行詳細代碼解析

本文件解讀 `highway_env/road` 目錄下的道路靜態障礙物與地標物件定義檔 `objects.py`。它負責描述除車輛以外，道路上存在的其它物理障礙物。

---

## 1. 道路物件基底類別：`RoadObject` (Lines 9 - 82)

```python
9: class RoadObject(ABC):
18:     LENGTH = 2.0  # 物件長度為 2.0 米
19:     WIDTH = 2.0   # 物件寬度為 2.0 米
```
* **初始化 (Lines 21-33)**：
  * 接收所屬道路實例，初始化絕對座標 $[x, y]$、速度、朝向角。
  * `self.hit = False`：預設撞擊標記為 `False`。一旦自駕車或背景車與其相撞，此標記會被置為 `True`。
* **在車道上生成物件 (Lines 35-46)**：
  * `make_on_lane`：接收車道 ID 和縱向行車距離，自動調用 `lane.position(longitudinal, 0)` 計算絕對 Cartesian 坐標並在此處實例化該物件。

```python
49:     def to_dict(self, origin_vehicle=None, observe_intentions=True):
50:         d = {
51:             'presence': 1,
52:             'x': self.position[0],
...
63:         if origin_vehicle:
64:             origin_dict = origin_vehicle.to_dict()
65:             for key in ['x', 'y', 'vx', 'vy']:
66:                 d[key] -= origin_dict[key]
67:         return d
```
* **狀態字典轉換與相對坐標投影 (Lines 49-67)**：
  * 為了讓 `KinematicObservation` 能夠像識別車輛一樣去識別障礙物，本函式提供了與 `Vehicle` 相同的 `to_dict` 接口。
  * **相對定位**：如果傳入自車 `origin_vehicle`，障礙物的坐標與速度會自動減去自車的對應物理量，轉化為**相對距離與相對速度**。這讓自駕大模型能夠通過文字 Prompt 感知到前方 30 米處存在一個靜止的障礙物。

---

## 2. 障礙物與地標子類別 (Lines 84 - 95)

```python
84: class Obstacle(RoadObject):
91: class Landmark(RoadObject):
```
* **`Obstacle` (障礙物)**：繼承自 `RoadObject`。代表路面上的實體障礙（如落石、事故壞車、修路路障），車輛不可穿過，撞擊會導致事故（crashed）。
* **`Landmark` (地標/路標)**：代表路面上的虛擬區域（如需要到達的指定交叉口、停車區、檢驗區），車輛可以物理穿過。常在環境中做為引導車輛開入的引導點，撞擊（即車輛中心與其重合）通常會觸發抵達目標的獎勵（arrived_reward）。
