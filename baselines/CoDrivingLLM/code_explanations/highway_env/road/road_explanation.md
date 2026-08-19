# CoDrivingLLM `highway_env/road/road.py` 逐行詳細代碼解析

本文件解讀 `highway_env/road` 目錄下的路網管理主檔案 `road.py`。它負責使用圖論（Graph Theory）建置路網拓撲，並管理仿真世界中所有車輛和障礙物的更新。

---

## 1. 路網拓撲結構類別：`RoadNetwork` (Lines 19 - 313)

`RoadNetwork` 將整個仿真地圖抽象化為一個**有向圖（Directed Graph）**：
* **節點（Nodes）**：道路交叉點或引道起點（如 `'o0'` 代表南口引道起點）。
* **邊（Edges）**：車道（`AbstractLane` 實體）。

```python
20:     graph: Dict[str, Dict[str, List[AbstractLane]]]
25:     def add_lane(self, _from: str, _to: str, lane: AbstractLane) -> None:
```
* **拓撲儲存 (Lines 20-37)**：使用雙層嵌套的 Dictionary `graph` 儲存路網結構。
  例如：`self.graph['o0']['ir0']` 返回一個列表，包含連接這兩個節點的所有平行車道幾何對象。

```python
51:     def get_closest_lane_index(self, position: np.ndarray, heading: Optional[float] = None) -> LaneIndex:
```
* **坐標反向車道匹配 (Lines 51-65)**：
  遍歷圖中的所有車道，計算車輛當前座標到每條車道中心線的幾何距離。回傳距離最近的車道 ID。這讓模擬器能實時知道車子「目前在幾號車道上」。

```python
216:     def shortest_path(self, start: str, goal: str) -> List[str]:
```
* **導航路徑規劃 (Lines 205-224)**：
  使用**廣度優先搜尋（BFS）**演算法。給定起點節點與目標出口節點，自動尋找兩點之間路口跳數最短的有向節點路徑。這在自駕車初始化時，被調用來生成 `ego_vehicle.plan_route_to(destination)` 全局導航路線。

```python
256:     def is_connected_road(self, lane_index_1: LaneIndex, lane_index_2: LaneIndex, route: Route = None,
257:                           same_lane: bool = False, depth: int = 0) -> bool:
```
* **衝突車道相連性檢測 (Lines 256-285)**：
  利用遞迴搜尋（深至 `depth` 層），檢測車道 2 是否會在自駕車規劃路線的下遊交匯。
  **作用**：在進行 TTC 預測時，自駕車只對未來會產生交疊相交的「相連車道」上的背景車計算碰撞時間，忽視那些背向行駛、絕不可能相撞的車輛，顯著優化了計算開銷。

---

## 2. 仿真道路與實體管理器：`Road` (Lines 316 - 467)

`Road` 類別是整個仿真世界的「實體容器」：

```python
316: class Road(object):
317:     def __init__(self, network: RoadNetwork = None, vehicles: List[Vehicle] = None, ...):
318:         self.network = network or RoadNetwork()
319:         self.vehicles = vehicles or []
320:         self.obstacles = obstacles or []
```
* **實體儲存**：維護當前道路上所有的車輛列表 `self.vehicles` 與障礙物列表 `self.obstacles`。
* **物理更新 Step (Lines 362-371)**：
  ```python
  def step(self, dt: float) -> None:
      for vehicle in self.vehicles:
          vehicle.step(dt)
  ```
  在每個時間步 `dt`，遍歷所有車輛實體，驅動它們執行基於單車模型的座標與速度積分遞推，推動世界前進。

```python
409:     def close_vehicles_to(self, vehicle: Vehicle, distance: float, count: int = None,
410:                           see_behind: bool = True) -> List[Vehicle]:
```
* **感知距離篩選 (Lines 409-444)**：
  給定目標車輛和最大感知半徑 `distance`，計算周圍所有車輛的幾何歐氏距離。
  篩選出該範圍內的車輛，並按照與自車的距離從近到遠進行排序。這被 `KinematicObservation` 調用，用來確定將哪些最鄰近的「高風險車輛」座標放入 Prompt 輸入給大模型。
