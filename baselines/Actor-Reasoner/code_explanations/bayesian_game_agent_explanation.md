# Actor-Reasoner `bayesian_game_agent.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下用於模擬人類駕駛（HDV）行為的賽局論決策器 `bayesian_game_agent.py`。它將對手視為不完全資訊的博弈參與者，通過求解不完全資訊下的一般純策略貝氏納許均衡（Bayesian Nash Equilibrium, BNE）來自主決策。

---

## 1. 貝氏代理人初始化與信念分佈 (Lines 14 - 40)

```python
14: class Bayesian_Agent:
15:     """solve 1v1 nash game for now"""
16:     def __init__(self, hdv_info, cav_info, action_type):
...
27:         self.aggressiveness_distribution = [0.14, 0.41, 0.45]  # ['agg', 'nor', 'con']
```
* **不完全資訊信念（Beliefs）**：
  HDV（人類駕駛）無法探知對方的真實駕駛風格，因此在初始化時維護一個對對手風格的**先驗概率分佈** `aggressiveness_distribution`。
  * `[0.14, 0.41, 0.45]` 分別對應對手是 `[激進, 正常, 保守]` 風格的概率。此概率會在互動中根據觀測數據被貝氏更新。

---

## 2. 賽局收益矩陣與納許均衡求解 (Lines 97 - 124)

```python
97:     def nash_equilibrium(self, inter_vehicle_aggressiveness):
98:         nash_matrix = np.zeros((Action_length, Action_length))
99:         ego_best_response, inter_best_response = self.get_best_response(...)
...
104:         _ = [i.tolist() for i in np.where(nash_matrix == 2)]
105:         nash = list(zip(*_))
106:         return nash
```
* **最佳反應（Best Response - Lines 108-124）**：
  `get_best_response` 遍歷自車 4 種加速度動作與對手 4 種加速度動作組成的 $4 \times 4$ 決策空間。計算自車收益矩陣 `ego_reward_matrix` 與對手收益矩陣 `inter_reward_matrix`。
  * 計算出給定對手動作時自車的最佳反應 `ego_best_response`，以及給定自車動作時對手的最佳反應 `inter_best_response`。
* **納許均衡判定 (Lines 100-106)**：
  如果一個動作組合 `(act1, act2)` 同時是自車對對手的最佳反應，也是對手對自車的最佳反應（即 `nash_matrix == 2`），則判定該狀態為一個**純策略納許均衡（Pure-strategy Nash Equilibrium）**。

---

## 3. 多項式複合效用函數計算：`reward` (Lines 126 - 165)

這是博弈求解中最關鍵的物理效用（Utility）指標：

```python
126:     def reward(self, act1, act2, inter_vehicle_aggressiveness):
```
* **第一項：橫向車道追蹤偏差（Lateral Deviation - Lines 131-141）**：
  計算車輛投影座標到地圖參考線的最小幾何偏離距離 `dis2cv`。偏離越遠，扣分越重。
* **第二項：行駛速度效益（Efficiency - Lines 142-145）**：
  正比於車輛的縱向行駛速度，速度越快，效率越高，加分。
* **第三項：目標進度效益（Progress - Lines 148-151）**：
  計算當前位置到全局路網出口終點 `destination` 的歐氏距離，負比關係（距離越遠扣分越多，鼓勵車輛向前開）。
* **第四項：安全 TTC 避讓懲罰（Safety - Lines 153-159）**：
  $$U_{\text{safety}} = -\frac{1}{\text{TTC} / \text{TTC}_{\text{thr}}}$$
  * `ttc_thr`（安全時間閾值）根據駕駛風格動態調整：激進型僅為 2 秒，保守型為 7 秒。當前車距與速差計算出的實際 TTC 越小，此安全懲罰項會呈倒數指數級暴增，迫使保守型車輛在博弈中主動踩煞車讓行。
* **效用矩陣加權 (Lines 161-165)**：
  將上述四個物理回報與專屬風格的權重向量 `Weight_hv` 進行點積（`np.dot`），得到最終綜合 payoff 收益。

---

## 4. 貝氏決策更新：`update_state` (Lines 73 - 95)

```python
73:     def update_state(self, output_action=False):
...
83:                 for ego_action in range(Action_length):
84:                     r[ego_action] += self.aggressiveness_distribution[inter] * \
85:                                      self.reward(ego_action, inter_pure_strategy, ...)[0]
86:             bayesian_pure_strategy = np.argmax(r)
```
* **期望收益最大化**：
  車輛在做出動作前，針對對手可能是 agg、nor 或 con 三種情況，分別求解出各自情況下的納許均衡對手動作 `inter_pure_strategy`。
  隨後，將自車的每一個動作在先驗分佈 `aggressiveness_distribution` 下求取**期望收益和（Expected Utility）**。最後，挑選出預期收益最大的那個加速度動作 `bayesian_pure_strategy` 執行，完成了經典的貝氏決策演化。
