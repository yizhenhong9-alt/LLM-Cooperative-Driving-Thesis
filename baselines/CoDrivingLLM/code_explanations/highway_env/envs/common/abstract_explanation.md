# CoDrivingLLM `highway_env/envs/common/abstract.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs/common` 目錄下最核心、代碼量最大的基礎環境類別檔 `abstract.py`。它繼承自 `gym.Env`，是所有自駕場景（直行、合流、路口）的底層物理與狀態分發基底。

---

## 1. 環境初始化與空間定義 (Lines 44 - 138)

```python
28: class AbstractEnv(gym.Env):
44:     def __init__(self, config: dict = None) -> None:
46:         self.config = self.default_config()
47:         if config:
48:             self.config.update(config)
...
56:         self.controlled_vehicles = []
...
63:         self.define_spaces()
```
* **初始化 (Lines 44-78)**：
  * 加載默認配置檔並進行更新。
  * 初始化車載列表 `controlled_vehicles`（儲存自駕車）與隨機數種子。
  * 呼叫 `define_spaces` 定義動作空間與觀測空間。
* **定義觀測與動作空間 (Lines 111-125)**：
  ```python
  def define_spaces(self) -> None:
      self.action_type = action_factory(self, self.config["action"])
      self.action_space = self.action_type.space()
      self.observation_type = observation_factory(self, self.config["observation"])
      self.observation_space = self.observation_type.space()
  ```
  * 通過工廠模式，根據動態配置加載動作對象（如離散的 `DiscreteMetaAction`）與觀測值對象（如 `KinematicObservation`），建立與 Gym 標準相容的 Space。

---

## 2. 仿真核心物理步進：`step` (Lines 197 - 251)

`step(action)` 負責接收高階指令，驅動底層多幀物理模擬，並返回 Gym 標準四元組：

```python
197:     def step(self, action: Action, env) -> Tuple[Observation, float, bool, dict]:
199:         self.steps += 1
200:         self._simulate(action)
```
* **物理仿真模擬 `_simulate(action)` (Lines 237-251)**：
  ```python
  def _simulate(self, action: Optional[Action] = None) -> None:
      if self.action_type:
          self.action_type.act(action)  # 注入動作（如轉化為油門加速度）
      for _ in range(self.config["simulation_frequency"] // self.config["policy_frequency"]):
          self.road.act()  # 計算背景車 IDM 決策
          self.road.step(1 / self.config["simulation_frequency"])  # 步進 0.05 秒物理積分
  ```
  * **解讀**：如果模擬頻率是 20Hz，決策頻率是 5Hz，則每一次 `step` 決策更新，底層物理引擎會連續循環步進 $20 / 5 = 4$ 次小步（每步 0.05 秒），累計向前推進 0.2 秒。

```python
202:         obs = self.observation_type.observe()
203:         reward = self._reward(action, obs, env)
204:         terminal = self._is_terminal()
205:         info = self._info(obs, action)
206: 
207:         return obs, reward, terminal, info
```
* **狀態收集與回傳**：
  * 調用觀測器獲取當前最新的車輛幾何相對矩陣 `obs`。
  * 計算當前狀態的回報值 `reward`、判斷是否結束 `terminal`，並將調試資訊打包進 `info` 中回傳。

---

## 3. 世界重置與畫面渲染 (Lines 265 - 340)

```python
265:     def reset(self) -> Observation:
268:         self.time = 0
269:         self.steps = 0
270:         self.done = False
271:         self._reset()
272:         self.define_spaces()
273:         return self.observation_type.observe()
```
* **重置 (Reset)**：清空仿真步數與計時器，呼叫子類別的實作函式 `_reset()`（重新繪製道路、重新生成車流），再次初始化動作觀測空間，並回傳開局首幀觀測狀態。

```python
287:     def render(self, mode: str = 'human') -> Optional[np.ndarray]:
296:         if not self.viewer:
297:             self.viewer = EnvViewer(self)
...
302:         self.viewer.display()
303:         return self.viewer.get_image()
```
* **渲染 (Render)**：如果開啟畫面繪製，本檔會實例化 `EnvViewer` 客戶端，調用 Pygame 繪製車身與軌跡，若模式設為 `rgb_array`，則將渲染影像以 RGB numpy 矩陣格式回傳，用於生成錄影影片。
