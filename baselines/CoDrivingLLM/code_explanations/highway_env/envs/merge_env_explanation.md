# CoDrivingLLM `highway_env/envs/merge_env.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs` 目錄下的 `merge_env.py`。如前所述，此檔案是專門為大模型設計的**數據解譯與 JSON 序列化工具檔**，而非 Gym 物理模擬環境本身。

---

## 1. 車道與車輛數據結構定義 (Lines 1 - 67)

本段利用 Python `dataclasses` 封裝了車道幾何與車輛特徵，方便導出 JSON。

```python
7: @dataclass
8: class Lane:
9:     id: str
10:     laneIdx: int
11:     left_lanes: List[str] = field(default_factory=list)
12:     right_lanes: List[str] = field(default_factory=list)
13: 
14:     def export2json(self):
15:         return {
16:             'id': self.id,
17:             'lane index': self.laneIdx,
18:             'left_lanes': self.left_lanes,
19:             'right_lanes': self.right_lanes,
20:         }
```

* **第 7-13 行**：使用 `@dataclass` 宣告車道類別。儲存車道 ID、索引，以及相鄰的左側車道與右側車道列表。
* **第 14-20 行**：`export2json()` 函式將車道拓撲結構轉換成標準 Dict，以便轉換為大模型輸入的背景路網描述。

```python
23: @dataclass
24: class Vehicle:
25:     id: str
26:     lane_id: str = ''
27:     x: float = 0.0
28:     y: float = 0.0
29:     speedx: float = 0.0
30:     speedy: float = 0.0
31:     presence: bool = False
```

* **第 23-31 行**：定義車輛特徵類別。儲存車輛 ID、所處車道、X座標（縱向距離）、Y座標（橫向車道位置）、縱/橫向車速、以及車輛是否存在標記（`presence`）。
* **第 41-49 行**：`updateProperty()` 函式實時更新車輛的位置與速度。特別是第 48-49 行：
  `laneIdx = round(y / 4.0)`
  `self.lane_id = 'lane_' + str(laneIdx)`
  它將幾何的 Y 座標值除以車道寬度 4.0 米並四捨五入，精準識別出車輛當前身處哪一條車道（`lane_0` 或 `lane_1`），完成了「數值坐標向語意車道」的對照。
* **第 59-67 行**：`export2json()` 函式將車輛 ID、車道、縱向位置及速度包裝成字典格式。

---

## 2. 場景解析器：`Scenario` 類別 (Lines 77 - 118)

此類別用於將當前模擬世界的狀態轉換為大模型可讀的全局 JSON。

```python
77: class Scenario:
78:     def __init__(self, road_info, vehicleCount: int,  database: str = None) -> None:
79:         self.lanes: Dict[str, Lane] = {}
80:         self.road_info =  road_info
81:         self.getRoadgraph()
82:         self.vehicles: Dict[str, Vehicle] = {}
83:         self.vehicleCount = vehicleCount
84:         self.initVehicles()
```

* **第 77-84 行**：接收模擬道路環境物件（`road_info`）與最大車輛數，自動呼叫 `getRoadgraph` 初始化車道拓撲，呼叫 `initVehicles` 初始化車輛映射字典（包含 `'ego'` 自車以及 `'veh1'`、`'veh2'` 等背景車）。

```python
89:     def export2json(self):
90:         scenario = {}
91:         scenario['lanes'] = []
92:         scenario['vehicles'] = []
93:         for lv in self.lanes.values():
94:             scenario['lanes'].append(lv.export2json())
95:         scenario['ego_info'] = self.vehicles['ego'].export2json()
96: 
97:         for vv in self.vehicles.values():
98:             if vv.presence:
99:                 scenario['vehicles'].append(vv.export2json())
100:         return json.dumps(scenario)
```

* **第 89-106 行**：**生成場景 JSON 字串**：
  遍歷所有車道與當前在場（`presence == True`）的車輛，調用各自的 `export2json` 函式。將它們彙整至一個大 Dict 中，最後使用 `json.dumps` 序列化輸出為 JSON 字串。
  這段輸出的字串會被發送給 `prompt_llm.py` 中，拼裝為 `Here is the current scenario: <JSON_String>`。

```python
107:     def which_lane(land_index):
109:         if land_index == ("j", "k", 0) or land_index == ("k", "b", 0) or land_index == ("b", "c", 1):
110:             return "lane_1"
111:         elif land_index == ("a", "b", 0) or land_index == ("b", "c", 0) or land_index == ("c", "d", 0):
112:             return "lane_0"
```

* **第 107-117 行**：車道索引映射器。接收模擬器中車道的起終點元組（如 `("b", "c", 1)` 對應匯入匝道段），將其轉換並歸類為更直觀的 `"lane_1"`（匝道/慢速道）與 `"lane_0"`（主線道）。
