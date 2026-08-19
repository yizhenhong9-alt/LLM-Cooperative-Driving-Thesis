# Actor-Reasoner `test_with_listener.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下結合語音語音聽寫監聽的測試檔 `test_with_listener.py`。它展示了如何將麥克風即時聽寫（Continuous Speech to Text）整合入快慢腦並行調度系統。

---

## 1. 語音監聽執行緒的並行派發 (Lines 114 - 129)

```python
114:     def update(self, frame):
...
125:         else:
126:             self.actor()
127:             self.executor.submit(self.listener)
128:             self.executor.submit(self.reasoner)
```
* **三頻並行調度 (Lines 125-128)**：
  在進入每一步更新時，執行緒池 `ThreadPoolExecutor` 會同時派發三個並行任務：
  1. **Actor 快速反射（主執行緒）**：毫秒級別完成向量經驗檢索，更新即時控制動作（油門/煞車）。
  2. **`submit(self.listener)`（語音聽寫線程）**：在後台異步啟動麥克風監聽。
  3. **`submit(self.reasoner)`（慢腦推理線程）**：在後台異步調用 Llama-3 進行局勢推理。

---

## 2. 語音監聽與指令注入：`listener` (Lines 166 - 176)

```python
166:     def listener(self):
167:         """即時監聽語音指令"""
168:         self.STT = ContinuousSpeechToText()
169:         time_start = time.time()
170:         if self.stop_threads:
171:             return
172:         self.instruction_info = self.STT.listen_and_convert()
```
* **異步語音獲取**：
  * 當語音監聽執行緒啟動時，它會調用 Google API 阻塞等待麥克風的人聲輸入。
  * 由於語音說話與網路識別通常需要數秒時間，**這段阻塞被完全分流在 `self.listener` 的背景執行緒中，不會阻礙物理世界和自車快腦 Actor 的每 0.1 秒步進**。
  * 一旦語音辨識成功返回（例如乘客說了 `"faster"`），大腦將變數 `self.instruction_info` 更新為 `"faster"`。
  * 此文字指令會立刻注入到後續步進中。在大模型 Reasoning Prompt 中，此指令會被寫入為：
    `Surrounding vehicle says: faster`
    大模型自駕車接收到語音指令後，會在後續決策中主動配合乘客或對手車的語音意圖，達成了高質量的語音意圖協同控制。
