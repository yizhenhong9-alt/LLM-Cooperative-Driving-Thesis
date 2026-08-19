# CoDrivingLLM `highway_env/envs/prompt_llm.py` 逐行詳細代碼解析

本文件解讀 `highway_env/envs` 目錄下的 `prompt_llm.py`。此檔案包含了大模型所使用的**基本提示詞工程範本、動作字典對照、以及格式化過濾裝飾器**。

---

## 1. 系統提示詞範本類別：`PRE_DEF_PROMPT` (Lines 1 - 36)

```python
5: class PRE_DEF_PROMPT():
10:     def __init__(self):
11:         self.SYSTEM_MESSAGE_PREFIX = """
12:     You are ChatGPT, a large language model trained by OpenAI.
13:     You are now act as a mature driving assistant, who can give accurate and correct advice for human driver in complex urban driving scenarios.
...
18:         self.TRAFFIC_RULES = """
19:     1. Try to keep a safe distance to the car in front of you.
20:     2. DONOT change lane frequently. If you want to change lane, double-check the safety of vehicles on target lane.
...
23:         self.DECISION_CAUTIONS = """
24:     1. You must output a decision when you finish this task. Your final output decision must be unique and not ambiguous...
```

* **第 11-16 行**：**系統角色設定（System Message Prefix）**：賦予大模型一個專業的角色定位——*「成熟的行車駕駛助理（mature driving assistant）」*，指令要求其為人類或自駕車在複雜城市路況下提供精準且正確的安全駕駛建議。
* **第 18-21 行**：**行車法規限制（Traffic Rules）**：大模型的動作必須約束在此規則內（例如：保持車距、禁止頻繁變道、變道前必須複查目標車道安全性）。
* **第 23-28 行**：**決策注意事項（Decision Cautions）**：
  * 規範輸出格式為唯一且不具歧義的標籤（不能給予模糊選擇）。
  * 要求大模型在決策前，必須牢記當前所在的車道 ID 和可執行的動作空間。
  * 要求大模型對受其決策影響的周圍所有鄰車進行安全評估。若判定不安全，必須從頭重寫。

---

## 2. 離散動作定義與語意映射 (Lines 40 - 54)

這兩個字典是「文字語意」與「數值控制」之間的橋樑：

```python
40: ACTIONS_ALL = {
41:     0: 'LANE_LEFT',
42:     1: 'IDLE',
43:     2: 'LANE_RIGHT',
44:     3: 'FASTER',
45:     4: 'SLOWER'
46: }
```
* 將大模型做出的語意決策，映射為 Gym 模擬器底層能直接執行的動作整數索引 `0` 至 `4`。

```python
48: ACTIONS_DESCRIPTION = {
49:     0: 'change lane to the left of the current lane,',
50:     1: 'remain in the current lane with current speed',
51:     2: 'change lane to the right of the current lane',
52:     3: 'accelerate the vehicle',
53:     4: 'decelerate the vehicle'
54: }
```
* **語意描述字典**：在將上一個時間步的動作歷史（Last Action）組裝進 Prompt 時，大模型需要閱讀具體的英文描述，而非冰冷的數字。此字典提供大模型看得懂的語意解釋（例如：將整數 `3` 翻譯為 `"accelerate the vehicle"` 餵給大模型）。

---

## 3. 提示詞裝飾器定義 (Lines 96 - 100)

```python
96: def prompts(name, description):
97:     def decorator(func):
98:         func.name = name
99:         func.description = description
100:         return func
```
* 建立了一個自定義的**提示詞註解器（Decorator）**。在開發自適應 prompt 時，可以透過 `@prompts(name="xx", description="xx")` 來標記不同的 Prompt 生成函式，方便系統動態篩選與組合最適合當前場景的提示模板。
