# Actor-Reasoner `test.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下核心測試模組 `test.py`。它完整實現了本研究最核心的**「快/慢腦並行調度架構（Actor-Reasoner Parallel Architecture）」**，在 step 物理步進中，利用多線程 thread pool 分流執行。

---

## 1. 並行調度器初始化 (Lines 72 - 89)

```python
72: class Simulator:
73:     def __init__(self, case_id, seed):
...
87:         self.executor = ThreadPoolExecutor(max_workers=2)
88:         self.file_name, self.workbook = open_excel(case_id)
```
* **Thread Pool 建立**：
  實例化一個最大容量為 2 的執行緒池 `ThreadPoolExecutor(max_workers=2)`。
  * 執行緒 1 用於跑主仿真的物理步進與 Actor 快速查表。
  * 執行緒 2 用於在背景異步執行 Reasoner 大模型推理。

---

## 2. 快/慢腦雙頻驅動 Step 更新 (Lines 114 - 146)

```python
114:     def update(self, frame):
...
125:         else:
126:             self.actor()
127:             self.executor.submit(self.reasoner)
```
* **快慢大腦分流 (Lines 125-128)**：
  在進入每一幀更新時：
  * **第一步：調用 Actor（快腦）**：
    呼叫 `self.actor()`。它在**主執行緒**中運行，以極快的速度檢索向量數據庫，即時返回最相似的 Few-shot 經驗動作，直接寫入控制端：
    `self.llm_output[0] = retrieved_memory[0][0]['final_action']`
    由於檢索時間極短（約 0.003 秒），這確保了物理仿真能維持 10Hz 實時運行。
  * **第二步：派發 Reasoner（慢腦）**：
    呼叫 `self.executor.submit(self.reasoner)`。它將 Reasoner 推理任務**提交至背景執行緒運行**。由於本地 Llama-3 推理耗時長達 2 至 5 秒，此分流保證了主執行緒不會被大模型推理卡死，維持了系統高頻更新。
* **物理模型積分**：
  使用當前快腦查表獲得的 action（`llm_output[0]`）控制自駕車，博弈算法控制背景車，兩車雙雙更新。

---

## 3. Actor 快腦查表與 Reasoner 慢腦推理實現 (Lines 147 - 167)

* **Actor（快腦 - Lines 147-156）**：
  ```python
  def actor(self):
      sce_descrip = tools.scenario_experience_generator(...)
      retrieved_memory = self.memory.retrieveMemory(query_scenario=sce_descrip, top_k=1)
      self.llm_output[0] = retrieved_memory[0][0]['final_action']
  ```
  * **解讀**：將當前狀態轉化為文本特徵，在 ChromaDB 進行快速相似度搜索，在毫秒級別直接覆寫 `'final_action'` 給 IDM 控制器，實現了直覺反射式的快速控制。
* **Reasoner（慢腦 - Lines 158-167）**：
  ```python
  def reasoner(self):
      if self.stop_threads: return
      output = self.agent.llm_run(..., if_train_mode=False)
      self.llm_output[1:] = output[1:]
  ```
  * **解讀**：在背景執行緒中緩慢推理，估計對手當前的行車意圖與駕駛風格（agg/con），並更新到全局變數 `self.llm_output[1:]` 中。
  * 雖然慢腦落後了數個物理時間步，但它一旦返回，就能修正自車對對手的意圖判斷，更新了 Actor 下一幀的檢索特徵（因為檢索特徵包含了慢腦估計的對手意圖與風格），達成了**「快腦做反射控制，慢腦做背景反思與信念修正」**的完美並行架構。
* 系統通過 `for case in range(case_num)` 執行 100 次不同亂數種子的案例測試，驗證雙腦模型的安全通關率。
