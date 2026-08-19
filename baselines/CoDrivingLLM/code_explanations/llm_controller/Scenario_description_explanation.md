# CoDrivingLLM `llm_controller/Scenario_description.py` 逐行詳細代碼解析

本文件解讀 `llm_controller` 目錄下的車型拓撲數據序列化檔 `Scenario_description.py`。它本質上是 `highway_env/envs/merge_env.py` 的解耦複製品，負責將數值座標數據提取並序列化為 JSON，供大模型作為實時場景文字輸入。

---

## 1. 車道與車輛屬性封裝 (Lines 7 - 67)

本段利用 Python `dataclasses` 封裝車道拓撲與車載狀態，提供導出至 Dictionary 的接口：

```python
7: @dataclass
8: class Lane:
9:     id: str
10:     laneIdx: int
...
14:     def export2json(self):
15:         return {
16:             'id': self.id,
17:             'lane index': self.laneIdx,
18:             'left_lanes': self.left_lanes,
19:             'right_lanes': self.right_lanes,
20:         }
```
* **車道節點**：儲存車道 ID 與索引，記錄其左側與右側相鄰車道以確定並行拓撲。

```python
24: class Vehicle:
25:     id: str
26:     lane_id: str = ''
27:     x: float = 0.0
28:     y: float = 0.0
41:     def updateProperty(self, x: float, y: float, vx: float, vy: float) -> None:
...
48:         laneIdx = round(y/4.0)
49:         self.lane_id = 'lane_' + str(laneIdx)
```
* **車載物特徵更新 (Lines 41-50)**：
  接收實時橫縱向座標與速度。使用 `round(y / 4.0)` 將橫向幾何座標換算為對應的整數車道索引（如 `y = 4` 對應 `lane_1`，`y = 0` 對應 `lane_0`），並賦予 `self.lane_id`。

---

## 2. 全局場景 JSON 輸出：`Scenario` (Lines 77 - 114)

```python
77: class Scenario:
78:     def __init__(self, road_info, vehicleCount: int,  database: str = None) -> None:
79:         self.lanes: Dict[str, Lane] = {}
80:         self.road_info =  road_info
...
87:     def export2json(self):
88:         scenario = {}
89:         scenario['lanes'] = []
90:         scenario['vehicles'] = []
...
95:         scenario['ego_info'] = self.vehicles['ego'].export2json()
96: 
97:         for vv in self.vehicles.values():
98:             if vv.presence:
99:                 scenario['vehicles'].append(vv.export2json())
103:         return json.dumps(scenario)
```
* **世界狀態打包 (Lines 87-103)**：
  遍歷所有車道和在場背景車。調用各自的 `export2json` 函式將對象轉為 dict，與自車的 `'ego_info'` 彙整後，使用 `json.dumps()` 壓製成 JSON 格式的字符串。
  **作用**：此 JSON 字符串是 LLM 理解當前有多少台車、它們各自身處哪條車道、速度多快的核心結構化數據來源。

---

## 3. 車道映射器 (Lines 105 - 114)

```python
105:     def which_lane(land_index):
107:         if land_index == ("j", "k", 0) or land_index == ("k", "b", 0) or land_index == ("b", "c", 1):
108:             return "lane_1"
109:         elif land_index == ("a", "b", 0) or land_index == ("b", "c", 0) or land_index == ("c", "d", 0):
110:             return "lane_0"
```
* 同樣提供匯入場景（Merge）中拓撲元組向語意車道 `"lane_0"`（主線道）與 `"lane_1"`（匝道/慢速道）的靜態映射。
