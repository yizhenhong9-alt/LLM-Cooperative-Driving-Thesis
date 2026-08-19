# Actor-Reasoner `llm_agent.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下大模型決策代理驅動檔 `llm_agent.py`。它負責建立 Llama-3 的本地腳本調用，並定義了雙向 Prompt 推理架構。

---

## 1. 本地大模型進程調用：`run_llama3` (Lines 7 - 18)

```python
7: def run_llama3(prompt):
8:     os.environ["QT_QPA_PLATFORM"] = "offscreen"
9:     process = subprocess.Popen(
10:         ["ollama", "run", "llama3"],  # 加載本地 Llama-3 模型
11:         stdin=subprocess.PIPE,
12:         stdout=subprocess.PIPE,
13:         text=True,
14:         encoding='utf-8'
15:     )
16:     output, _ = process.communicate(input=prompt)
17:     return output
```
* **Ollama 子進程調用**：
  這是針對 Ollama 本地部署的調用方式。系統不使用 HTTP 請求，而是直接通過 Python `subprocess.Popen` 開啟一個命令行進程 `ollama run llama3`。
  通過進程管道（Pipes）將組裝好的 Prompt 字串寫入 `stdin`，並阻塞等待其完成推理後自 `stdout` 讀取回傳的回答文本。

---

## 2. 雙向決策 Prompt 模板 (Lines 47 - 108)

大模型的決策 Prompt 分為兩種模式：

### A. 訓練加載模式（if_train_mode = True - Lines 50-83）
此模式在大模型 Prompt 中加入了思維鏈（CoT, Chain-of-Thought）引導，要求 Llama-3 必須輸出 `thoughts` 思考過程，詳細回答以下問題：
1. 對手車在做什麼動作？其真實意圖是 ACCELERATE 還是 DECELERATE？
2. 基於其動作，估計對手的駕駛風格是 AGGRESSIVE 還是 CONSERVATIVE？
3. 為了安全與效率，自車應該採取什麼動作（IDLE, FASTER, SLOWER）？
4. 最終要共享給對方的行車意圖語句是什麼？
* **輸出格式**：嚴格要求以 JSON 語法格式返回思考過程與離散決策標籤。

### B. 生產測試模式（if_train_mode = False - Lines 84-108）
為了縮短 Llama-3 本地推理的 Token 長度和生成時間（提升運算效率），此模式在 Prompt 中移除了 thoughts 引導，並用強烈警告：*“DO NOT OUTPUT YOUR THOUGHTS”* 指令大模型直接輸出 JSON 決策結果，這能縮減 70% 的 Token 生成開銷。

---

## 3. 輸出結構化提取與安全記憶寫入 (Lines 118 - 194)

* **動作與意圖提取 (`extract_output` - Lines 118-156)**：
  使用 Python 字串尋找 `find()` 與特徵標籤（如 `"decision": {`），切片提取出大模型做出的控制決策、HMI 意圖語句、以及對對手的意圖和風格估計。
* **物理安全反思寫入 (`add_memory2dataset` - Lines 167-194)**：
  這是 Actor-Reasoner 自主學習的核心邏輯：
  * 當大模型產出動作（如加速）時，系統會在背景複製一份當前的車載狀態，向前模擬前進一步，計算下一步的未來相對 $\Delta TTCP$。
  * **寫入安全經驗條件**：
    * 如果兩車目前處於極度高風險的衝突區（`abs(current_delta_ttcp) > 5`）。
    * 或者，下一步的 $\Delta TTCP$ 絕對值比當前更大（代表大模型做出的這個決策**導致了兩車在衝突點的抵達時間差進一步縮小，碰撞風險增加**）。
    * 此時，系統會判定這是一個**「安全關鍵場景（Safety-critical Scenario）」**，並立刻呼叫 `memory_tools.addMemory` 將這個場景的特徵與最終動作強制寫入 ChromaDB 向量數據庫，完成了一次基於物理衝突反省的經驗積累。
