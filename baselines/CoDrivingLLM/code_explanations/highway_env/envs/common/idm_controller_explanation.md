# CoDrivingLLM `highway_env/envs/common/idm_controller.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下的經典交通跟車與變道控制器 `idm_controller.py`。它是模擬器中所有**背景人類駕駛車（HDV）**的底層物理驅動模型。

---

## 1. 動作生成主流程：`generate_actions` (Lines 59 - 77)

此函式在每個模擬步進執行，自動為背景車輛計算下一步的方向盤與油門：

```python
59: def generate_actions(vehicle, env_copy):
61:     front_vehicle, rear_vehicle = neighbour_vehicles(vehicle, env_copy)
```
* **步驟一：尋找鄰居車輛 (`neighbour_vehicles`)**：
  在當前車道的前後搜尋，定位出距離最近的先行車 `front_vehicle` 和後跟車 `rear_vehicle`。
* **步驟二：橫向變道決策 (`change_lane_policy`)**：
  呼叫 `change_lane_policy()`（底層基於 **MOBIL** 變道模型），判定是否需要變道並輸出目標車道 ID。隨後呼叫 `steering_control()`（比例控制器）計算方向盤轉角：
  `action['steering'] = steering_control(...)`
* **步驟三：縱向速度控制 (`acceleration`)**：
  調用 **`acceleration(...)`**（底層基於 **IDM** 跟車模型），計算期望油門加速度值。
* **步驟四：加入隨機雜訊並注入**：
  在控制量上乘以隨機波動雜訊（模擬人類開車的不確定性），最後存入 `vehicle.action` 中，等待物理仿真更新。

---

## 2. 經典跟車模型：`IDM (Intelligent Driver Model)` (Lines 201 - 229)

IDM 透過以下數學公式，兼顧「達到期望速度」與「防範碰撞安全距離」來計算車輛加速度：

```python
221:     acceleration = COMFORT_ACC_MAX * (1 - np.power(max(ego_vehicle.speed, 0) / ego_target_speed, DELTA))
```
* **期望速度項**：當前車速離目標車速越遠，此項越接近最大舒適加速度 `COMFORT_ACC_MAX`；若已達到速限，此項歸零。

```python
226:         acceleration -= COMFORT_ACC_MAX * np.power(desired_gap(ego_vehicle, front_vehicle) / utils.not_zero(d), 2)
```
* **期望安全車距項**：計算安全車距 `desired_gap` 與實際车距 `d` 的比值平方。
  * `desired_gap` 公式 (Lines 284-290)：
    $$d^* = d_0 + v \cdot T + \frac{v \cdot \Delta v}{2 \sqrt{a b}}$$
    包含：静止安全車距 $d_0$、反應時距距離 $v \cdot T$、以及兩車速差制動距離。
  * 若實際車距 $d$ 小於安全車距 $d^*$，此懲罰項會迅速膨脹，使加速度變為大負值，車輛執行重踩煞車。

---

## 3. 經典變道模型：`MOBIL` (Lines 126 - 167)

MOBIL 是一套「利己且利他」的變道物理決策算法：

```python
126: def mobil(vehicle, env_copy):
```
* **安全性判定 (Safety Constraint - Lines 137-142)**：
  計算一旦自車變道過去，新車道上的後跟車（`new_following`）被迫產生的最大煞車減速度。如果該減速度超出了極限閾值 `LANE_CHANGE_MAX_BRAKING_IMPOSED = 9.0 m/s²`，則判定為**不安全切入（Cut-in）**，強行否決變道。
* **合理性判定 (Liveness / Incentive - Lines 156-164)**：
  計算變道為自車和周圍車輛帶來的加速度效益之和：
  $$\text{Jerk} = (a_{\text{自, 變}} - a_{\text{自, 原}}) + p \cdot (a_{\text{新後, 變}} - a_{\text{新後, 原}} + a_{\text{舊後, 變}} - a_{\text{舊後, 原}})$$
  其中 $p$ 為**利他係數（POLITENESS）**。如果變道產生的總加速度增益大於臨界值 `LANE_CHANGE_MIN_ACC_GAIN = 0.1`，則同意執行變道。
