# CoDrivingLLM `highway_env/vehicle/behavior.py` 逐行詳細代碼解析

本文件解讀 `highway_env/vehicle` 目錄下的車輛行為決策策略檔 `behavior.py`。它定義了如何使用經典 IDM (跟車) 與 MOBIL (變道) 機制，使車輛在無外部輸入的情況下實現全自主安全駕駛。

---

## 1. 經典自主跟車與變道車輛類別：`IDMVehicle` (Lines 13 - 289)

`IDMVehicle` 繼承自 `ControlledVehicle`。它覆蓋了 `act()` 方法，將微觀決策完全交由內建的模型求解：

* **完全自主行為 (Lines 74-101)**：
  在 `act()` 中，它會自動呼叫：
  * `front_vehicle, rear_vehicle = self.road.neighbour_vehicles(self)` 獲取前後鄰車。
  * `self.change_lane_policy()`：利用 MOBIL 變道模型評估是否需要並執行變道，更新目標車道 `self.target_lane_index`。
  * `self.acceleration(...)`：利用 IDM 模型求解期望加速度，限制在 `[-ACC_MAX, ACC_MAX]`，最終打包為底層 PID 的目標物理量。
* **變道防重複校驗 (Lines 196-210)**：
  如果車輛已經在變道過程中（`lane_index != target_lane_index`），且檢測到有其它受控車正在朝同一車道併線，為了防止兩車相撞，它會檢測車距。如果距離過近，則會**中止變道，將目標車道改回當前車道**。
* **倒車脫困機制 (`recover_from_stop` - Lines 269-287)**：
  如果車輛在錯誤的車道上被卡住停下（`speed < 5 m/s`），在確認後方車道空曠安全的情況下，車輛會執行倒退操縱（輸出負的舒適加速度值），以嘗試挪動車位重新出發。

---

## 2. 線性參數化車輛類別：`LinearVehicle` (Lines 290 - 476)

```python
290: class LinearVehicle(IDMVehicle):
293:     ACCELERATION_PARAMETERS = [0.3, 0.3, 2.0]
```
* **線性控制特徵 (Lines 330-364)**：
  * 正規的 IDM 是高度非線性的。而 `LinearVehicle` 嘗試使用**線性特徵組合**來近似逼近 IDM 與橫向 PID 控制。
  * `acceleration_features` 提取三個線性特徵：`[目標車速偏差 vt, 與前車速差 dv, 距安全車距之偏差 dp]`。將這些特徵與權重陣列 `ACCELERATION_PARAMETERS` 做點積，求得加速度。
  * 同理，`steering_features` 提取與中心線朝向偏差和橫向位移偏差，做點積得到轉向角。這常用於通過回歸分析（Regression）擬合人類駕駛參數。

---

## 3. 多樣駕駛風格子類別 (Lines 478 - 496)

藉由調整 `LinearVehicle` 的引數參數，直接派生出不同駕駛風格的車載實體：

### A. 激進型車輛 (`AggressiveVehicle` - Lines 478-485)
* 最小變道加速度收益閾值 `LANE_CHANGE_MIN_ACC_GAIN` 設為大值，但跟車間距係數（最後一個參數）設為 `0.5`（極小）。這意味著**它願意貼前車貼得非常緊，喜歡頻繁加塞和超車**。

### B. 防禦型安全車輛 (`DefensiveVehicle` - Lines 488-496)
* 跟車間距係數設為 `2.0`（極大），安全車頭時距 `TIME_WANTED` 設為 2.5 秒。這意味著**它極其保守，始終與前車拉開極大的安全避讓距離，開得極為謹慎**。
