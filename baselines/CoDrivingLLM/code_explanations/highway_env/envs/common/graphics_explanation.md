# CoDrivingLLM `highway_env/envs/common/graphics.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下的視覺渲染器與事件處理檔 `graphics.py`。它使用 Pygame 繪製仿真世界，並支持手動鍵盤接管車輛控制。

---

## 1. 核心視覺視窗渲染器：`EnvViewer` (Lines 16 - 150)

```python
16: class EnvViewer(object):
22:     def __init__(self, env: 'AbstractEnv') -> None:
23:         self.env = env
24:         self.offscreen = env.config["offscreen_rendering"]
```
* **初始化 (Lines 22-38)**：
  * 初始化 Pygame 視窗，讀取長寬設定。
  * `offscreen_rendering`：如果開啟離屏渲染，則跳過顯示器載入，直接在隱形畫布（Surface）上繪圖。這對於雲端跑圖、無螢幕的 Linux 伺服器訓練至關重要。
* **動作預測與軌跡繪製 (`set_agent_action_sequence` - Lines 69-81)**：
  如果傳入動作序列，自車會調用 `predict_trajectory()` 預先計算出未來數步的動態軌跡坐標，並由 `VehicleGraphics.display_trajectory` 以彩色軌跡線條渲染在螢幕上。
* **螢幕更新 Blit 與存檔 (Lines 126-134)**：
  `self.screen.blit(self.sim_surface, (0, 0))`。將繪有道路、車輛和軌跡的局部畫布貼上主視窗，刷新螢幕。如果開啟 `SAVE_IMAGES`，則將當前幀保存為 `.png` 圖片，用於後期合成為影片。
* **影像陣列抓取 (Lines 136-140)**：
  ```python
  136:     def get_image(self) -> np.ndarray:
  139:         data = pygame.surfarray.array3d(surface)
  140:         return np.moveaxis(data, 0, 1)
  ```
  利用 `pygame.surfarray.array3d` 直接抓取顯存中的 3D RGB 圖像矩陣，並調整維度順序。這正是主程式中 `env.render('rgb_array')` 獲取幀數據來壓製成 `.mp4` 影片的底層實現。

---

## 2. 鍵盤事件控制接管：`EventHandler` (Lines 151 - 200)

此模組允許研究人員在模擬運行中，直接使用鍵盤方向鍵手動開車，覆蓋大模型的輸出：

```python
151: class EventHandler(object):
152:     @classmethod
153:     def handle_event(cls, action_type: ActionType, event: pygame.event.EventType) -> None:
```

* **離散動作鍵盤映射 (Lines 166-176)**：
  若環境使用 `DiscreteMetaAction`，它會監聽鍵盤按下事件：
  * **右方向鍵 (`K_RIGHT`)** $\rightarrow$ 發送加速指令 `FASTER`
  * **左方向鍵 (`K_LEFT`)** $\rightarrow$ 發送減速指令 `SLOWER`
  * **上方向鍵 (`K_UP`)** $\rightarrow$ 發送左變道指令 `LANE_LEFT`
  * **下方向鍵 (`K_DOWN`)** $\rightarrow$ 發送右變道指令 `LANE_RIGHT`
* **連續動作鍵盤映射 (Lines 178-199)**：
  若使用 `ContinuousAction`（方向盤與油門控制），它會捕捉按鍵的按下（`KEYDOWN`）與釋放（`KEYUP`）狀態，微調 `throttle`（前後油門 `0.7` 或 `-0.7`）與 `steering`（左右轉向角），釋放按鍵時自動歸零，完美契合賽車遊戲的鍵盤操控邏輯。
