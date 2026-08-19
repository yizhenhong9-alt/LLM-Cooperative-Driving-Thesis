# CoDrivingLLM `llm_controller/prompt_llm.py` 逐行詳細代碼解析

本文件解讀 `llm_controller` 目錄下的提示詞模板與規則校驗引擎主檔 `prompt_llm.py`。它是整個專案中最龐大的程式碼之一，包含了各種高低階提示詞模板、車載安全規則評估模組。

---

## 1. 系統提示詞範本與規則：`PRE_DEF_PROMPT` (Lines 6 - 59)

* 包含直行公路（`SYSTEM_MESSAGE_PREFIX`）與十字路口（`SYSTEM_MESSAGE_PREFIX_intersection`）兩種不同的系統提示詞。
* **路口縱向限制 (Lines 40-51)**：
  大模型在路口環境下被嚴格限制了車道切換：
  * *“Remember you can't change your lane... you just can choose three kinds of actions: IDLE, FASTER, SLOWER.”*

---

## 2. 工具模型與微觀安全規則校驗類別 (Lines 105 - 744)

本檔定義了數個安全校驗類別，充當了自駕車大腦的「安全物理規則盾」：

### A. 可行車道掃描：`getAvailableLanes`
* **作用**：解析路網拓撲圖。輸出自駕車當前的車道 ID，並確認左側、右側是否還存在物理車道，將其轉化為文字 Prompt。

### B. 鄰車幾何提取：`getLaneInvolvedCar`
* **作用**：在當前車道及相鄰左右車道上，搜尋距離自車最近的先行車（`leadingCar`）與後跟車（`rearingCar`）。
* **文字生成**：計算並輸出鄰車的 ID、相對距離（$dx$）和相對速度差（$dv$）。如果無車，輸出 `'None'`。

### C. 變道安全檢測：`isChangeLaneConflictWithCar` (MOBIL 的大模型文字版)
* **作用**：模擬大模型變道時的安全性。
* **物理規則**：
  * **目標前車**：若變道後的目標車道前車與自車的 TTC（時間差）太小，判定為危險。
  * **目標後車**：若變道後會導致目標後車被迫產生大於 $3 m/s^2$ 的煞車，判定為危險並輸出：
    `"it is unsafe to change lane... which may cause rear-end collision of vehX."`
  * **綠色安全放行**：只有當左右變道確認無衝突時，才放行，引導大模型安全變道。

### D. 縱向速度校驗組 (Longitudinal Checks)
* **加速安全檢測 (`isAccelerationConflictWithCar`)**：
  * 如果自車加速，計算與前車的預計碰撞時間（TTC）。如果 $TTC < 1.5$ 秒，安全盾會報警：
    `"acceleration may cause conflict with vehX, which is unacceptable."`
* **減速安全性 (`isDecelerationSafe`)**：
  * 校驗自車如果減速，是否會遭到當前車道後車追尾。

### E. 全域交警衝突約束校驗：`check_safety_with_conflict_vehicles`
* 接收來自 `llm_agent_negotiation_system.py` 的交警通行指示。
* **協作讓行約束**：
  * 若交警建議 Passes Second（後過/讓行），本模組會將該衝突車輛標記為「最危險車輛（Most Dangerous Vehicle）」，並產生強制警告：
    `"You are recommended to PASSES SECOND... you must SLOW DOWN to yield to vehX!"`
    這強制引導大模型的決策神經元產生減速避讓動作，達成了 V2X 安全協同。
