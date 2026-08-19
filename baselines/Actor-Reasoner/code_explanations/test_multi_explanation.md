# Actor-Reasoner `test_multi.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下用於評估「多車交會博弈」場景的測試檔 `test_multi.py`。它將 1v1 的貝氏博弈與快慢腦模型擴展至包含多輛背景車與自駕車的複雜路網中。

---

## 1. 最具威脅對手篩選 (Lines 100 - 108)

```python
101:         if tools.if_passed_conflict_point(self.cav_info, self.opponent):
102:             self.llm_output[0] = 'FASTER'
```
* **對手篩選**：
  在多車環境下，路口可能有多台車輛同時行駛。自駕車不可能同時和所有車子談判，因此在 `update` 中呼叫：
  `self.opponent = tools.find_opponent(self.cav_info, self.hdv_info)`
  * **最具威脅車輛**：`find_opponent` 會計算所有未通過交點的車輛與 CAV 的 $\Delta TTCP$。挑選出**時間差最小、碰撞風險最高的那台車**作為主要博弈對手 `self.opponent`。
  * 自駕車的 Actor（快腦）和 Reasoner（慢腦）將聚焦於這台最危險的車輛進行特徵提取與推理。

---

## 2. 背景人類駕駛的多車相互博弈 (Lines 114 - 124)

本段是多車博弈演化的核心實現：

```python
114:         temp_hdv_info = []
115:         for hdv in self.hdv_info:
116:             opp_list = list(copy.deepcopy(self.hdv_info))
117:             opp_list.append(self.cav_info)
118:             opp_list = [veh for veh in opp_list if veh != hdv]
119:             game_opp  = tools.find_opponent(hdv, opp_list)
120:             bayesian_agent = Bayesian_Agent(hdv, game_opp, action_type='discrete')
121:             temp_hdv_info.append(bayesian_agent.update_state())
```
* **多車賽局演化 (Lines 114-121)**：
  背景車（HDV）之間也會相互影響與避讓。因此，系統為每一台背景車 `hdv`：
  * **第一步：建立對手池**：將其它所有背景車與 CAV 合併，排除該 `hdv` 本體，得到其潛在的對手列表 `opp_list`。
  * **第二步：選定對手**：呼叫 `find_opponent` 尋找與該 `hdv` 衝突風險最高的那一台車 `game_opp`。
  * **第三步：求解貝氏均衡**：實例化一個獨立的 `Bayesian_Agent` 博弈求解器，計算出該 `hdv` 的最佳加速度，推動其狀態更新。
* **物理世界同步更新 (Lines 123-130)**：
  更新所有博弈背景車與 CAV 的物理位置。將所有車輛的數值坐標與意圖寫入 Excel 保存，完成多車交會的仿真。
