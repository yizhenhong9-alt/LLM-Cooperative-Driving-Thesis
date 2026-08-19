# CoDrivingLLM `highway_env/vehicle/graphics.py` 逐行詳細代碼解析

本文件解讀 `highway_env/vehicle` 目錄下的車輛 Pygame 繪圖與視覺效果渲染檔 `graphics.py`。它負責定義車輛在 GUI 視窗中的外觀色調、前輪轉向動態以及歷史軌跡虛影。

---

## 1. 高質感現代配色調色盤 (Lines 27 - 46)

相較於原版 `highway-env` 刺眼的純紅、純綠，本專案重新調製了融合了現代 UI 審美的莫蘭迪色系：

* **`RED` (紅/事故車)** $\rightarrow$ `(183, 62, 62)`（低飽和暗紅）
* **`GREEN_LIGHT` (自駕車/CAV)** $\rightarrow$ `(144, 238, 144)`（柔和淺綠）
* **`BLUE` (目標引導車)** $\rightarrow$ `(154, 220, 255)`（天空冰藍）
* **`BLACK` (車體輪廓線/輪胎)** $\rightarrow$ `(128, 138, 135)`（冷灰石色）
* **`GREY_SHADOW` (背景人類車/IDM)** $\rightarrow$ `(154, 154, 152)`（陰影軟灰）

---

## 2. 車輛實體繪製與輪胎轉向：`display` (Lines 48 - 103)

```python
48:     def display(cls, vehicle: Vehicle, surface: "WorldSurface", ...):
69:         vehicle_surface = pygame.Surface((surface.pix(length), surface.pix(length)), flags=pygame.SRCALPHA)
70:         rect = (surface.pix(tire_length), surface.pix(length / 2 - v.WIDTH / 2), surface.pix(v.LENGTH), surface.pix(v.WIDTH))
71:         pygame.draw.rect(vehicle_surface, cls.get_color(v, transparent), rect, 0)
```
* **車身繪製 (Lines 67-73)**：
  實例化一個支持透明通道（`SRCALPHA`）的 Surface，調用 `pygame.draw.rect` 繪製出車身實心矩形，並搭配 `get_color(v)` 自動判斷車輛類型塗色，外圈繪製一像素寬的灰色輪廓線。
* **輪胎差速轉向 (Lines 74-86)**：
  ```python
  80: tire_angles = [0, 0, v.action["steering"], v.action["steering"]]
  ```
  系統在車身四角生成輪胎。**特別是前輪（第 3、4 個輪胎），其旋轉偏角被綁定為自駕車或 IDM 控制器當前的方向盤控制量 `steering`**。調用 `blit_rotate` 讓前輪在畫布上發生轉動，這使得車輛在轉彎變道時能看到輪胎指向的擬真動態。
* **車輛旋轉疊加 (Lines 87-94)**：
  計算車身偏航朝向角 `h`（轉換為角度），將車輛畫布進行對中旋轉，隨後貼上（`blit`）到全域地圖 Surface 上。

---

## 3. 車身軌跡與歷史虛影渲染 (Lines 133 - 162)

* **軌跡虛影 (`display_history`)**：
  ```python
  157: for v in itertools.islice(vehicle.history, ...):
  161:     cls.display(v, surface, transparent=True, offscreen=offscreen)
  ```
  遍歷車輛保存的 30 幀歷史隊列，調用 `display`。但此處將 `transparent` 設為 `True`，即給予車身一個極低的 Alpha 透明度值 `(..., 30)`。這會在自駕車身後渲染出一串半透明的「幽靈虛影（Ghosting Trail）」，極大地增強了變道時的視覺軌跡質感。
