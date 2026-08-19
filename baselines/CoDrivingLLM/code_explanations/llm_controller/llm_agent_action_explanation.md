# CoDrivingLLM `llm_controller/llm_agent_action.py` 逐行詳細代碼解析

本文件解讀 `llm_controller` 目錄下最核心的車載自駕決策模組檔 `llm_agent_action.py`。它負責為每一台自駕車（CAV）實例化提示詞工程、融入全域談判成果、調用相似先驗經驗、並最終產出具體的離散動作決策。

---

## 1. 大模型控制決策入口：`llm_controller_run` (Lines 47 - 63)

```python
47:     def llm_controller_run(self, env, negotiation_prompt, conflicting_info, controlled_vehicles, memory):
48:         llm_actions = []
49:         for i, ego_veh in enumerate(controlled_vehicles):
...
56:             negotiation_results = self.transfer_negotiation_prompts_to_results(ego_veh, negotiation_prompt)
57:             prompt_info = self.prompt_engineer(ego_veh, env.road, env, negotiation_results, conflicting_info)
58:             llm_action = self.send_to_chatgpt(ego_veh, prompt_info, negotiation_results, memory)
59:             self.memory_update(memory, prompt_info, llm_action)
```
* **多自駕車巡檢 (Lines 49-62)**：
  迴圈遍歷每一台需要大模型控制的 CAV 車輛。
  * **第一步：解析交警指令**：呼叫 `transfer_negotiation_prompts_to_results`，解析全域虛擬交警的談判指令（`negotiation_prompt`），提取出針對該車的專屬建議（如：“你與 veh1 衝突，建議你 passes second（後過）”）。
  * **第二步：提示詞工程建置**：呼叫 `prompt_engineer`（內部融合物理安全规则檢測）產出當前場景的詳細文本描述 `prompt_info`。
  * **第三步：決策生成**：呼叫 `send_to_chatgpt` 發送至大模型（OpenAI/Ollama），返回高階動作指令（如 `[3]` 即加速）。
  * **第四步：數據庫更新**：呼叫 `memory_update` 將本次決策存入 ChromaDB 向量經驗庫。

---

## 2. 歷史經驗檢索與更新 (Lines 136 - 158)

```python
136:     def relative_memory(self, memory, prompt_info):
138:         extract_prompt = prompt_info.strip().split('\n')
139:         query_scenario = '\n'.join(extract_prompt[-2:])
140:         past_decisions = memory.retrieveMemory(query_scenario, top_k=2)
```
* **語意特徵定位 (Lines 136-144)**：
  自 `prompt_info` 中截取最後兩行（包含最危險的衝突幾何描述）作為檢索 key。呼叫 Vector DB 尋找最相近的兩個歷史記憶，組裝成 few-shot 文字段注入 Prompt。
* **安全性自我評論更新 (`memory_update` - Lines 146-158)**：
  ```python
  153: comments = generate_comment(relation[0], llm_action[0])
  157: memory.addMemory(..., comments)
  ```
  決策執行後，系統會結合當前衝突關係 `relation` 與大模型實際動作 `llm_action` 進行自我審視。例如，如果交警命令讓行，大模型卻選擇了加速，評論會標記為 `'bad decision'`，如果順利讓行則標記為 `'good decision'`。這極大地幫助了後續的回合進行安全閉環。

---

## 3. 提示詞工程框架：`prompt_engineer` (Lines 250 - 270)

此函式是組裝大模型文字輸入的工廠：

```python
250:     def prompt_engineer(self, ego_veh, road, env, negotiation_results, conflicting_info):
253:         msg0 = available_action(self.toolModels, ego_veh, road, env)
254:         availabel_lane, msg1 = get_available_lanes(self.toolModels, ego_veh, road, env)
255:         msg2, lane_cars_id = get_involved_cars(self.toolModels, ego_veh, road, env, availabel_lane)
```
* 依序調用提示詞模板工具：
  * `msg0`：可行動作描述（LANE_LEFT, IDLE, 等）。
  * `msg1` / `availabel_lane`：自車當前所處車道與左右相鄰車道。
  * `msg2` / `lane_cars_id`：前車與後車的存在性、距離、車速。
  * `safety_assessment`：變道的物理安全評估（是否會導致 Cut-in 碰撞）。
  * `safety_msg`：當前車道縱向運動安全評估（若維持目前速度、加速、減速，是否會追尾）。
  * `safety_msg2` / `most_dangerous_info`：大模型談判模組與 V2X 的衝突車輛引導。
  * `format_training_info`：將上述所有檢測文字彙整拼接，回傳作為最優提示詞。
