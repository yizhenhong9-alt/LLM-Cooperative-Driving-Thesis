# Actor-Reasoner `memory.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下核心的經驗數據庫接口檔 `memory.py`。它實現了論文中最關鍵的**「雙層檢索架構（Two-Layer Retrieval）」**與**「對手駕駛風格分庫路徑（Style Partitioning）」**。

---

## 1. 本地輕量向量嵌入：`EmbeddingWrapper` (Lines 12 - 36)

```python
12: class EmbeddingWrapper:
13:     def __init__(self, model_name_or_path):
14:         self.model = SentenceTransformer(model_name_or_path)
```
* **本地 SentenceTransformer 嵌入**：
  不調用昂貴的 OpenAI 線上接口。本檔在初始化時會檢測本地 `model/all-MiniLM-L6-v2/` 路徑。若不存在，則自動從鏡像站下載 HuggingFace 開源的輕量級句子特徵嵌入模型 `all-MiniLM-L6-v2` 並持久化保存，隨後使用 `EmbeddingWrapper` 對文字進行向量特徵計算。

---

## 2. 駕駛風格分庫加載：`load_memories` (Lines 38 - 52)

```python
39:         for memory_type in ["normal", "aggressive", "conservative"]:
40:             self.memory_by_type[memory_type] = Chroma(
41:                 embedding_function=self.embedding,
42:                 persist_directory=f'./db/{Scenario_name}/{memory_type}'
43:             )
```
* **風格記憶分區**：
  這是學術創新點。專案並沒有把所有記憶混為一談，而是針對人類駕駛風格分為 **`normal` (正常), `aggressive` (激進), `conservative` (防禦型)** 三個獨立的 Chroma 數據庫文件夾，分別存在地圖路徑下（如 `./db/roundabout/aggressive`）。
  * `determine_memory_type(sce_descrip)` 正則分析當前車輛估算的對手風格，並以此動態路由到對應的分區數據庫進行讀寫。

---

## 3. 【核心學術貢獻】雙層檢索機制：`retrieveMemory` (Lines 53 - 112)

為了應對自駕系統中數值特徵（距離、車速）與語意特徵（交警指令、對手意圖）在 Embedding 中的表示差異，系統實施了兩層過濾機制：

```python
75:     def retrieveMemory(self, query_scenario, top_k):
77:         query_value = self.extract_numeric_value(query_scenario)
```
* **第一層：定量數值粗篩（Quantitative Layer - Lines 53-74）**：
  * `extract_numeric_value`：從狀態描述中提取浮點數陣列：`[是否有指令, 自車剩餘距離, 兩車TTCP差, 兩車距交點距離差, 兩車速差]`。
  * `find_closest_numbers`：計算目前數值陣列與數據庫中全體歷史經驗的加權 Euclidean 距離（特別給予反應通行順序的「指令項」最大權重 10）：
    `weighted_distance = sum(weights[i] * abs(input_numbers[i] - num[i]))`
    找出數值特徵最接近的 top-10 個經驗的 ID（`closest_indices`）。

```python
83:         query_text = self.remove_numbers(query_scenario)
85:         similarity_results = self.memory_by_type[memory_type].similarity_search_with_score(
                query_text, k=top_k, filter={'id':{'$in':closest_indices}})
```
* **第二層：定性語意精篩（Qualitative Layer - Lines 83-92）**：
  * `remove_numbers`：**使用正則濾除文本中所有的阿拉伯數字**（避免數值噪聲干擾 Embedding 特徵）。
  * **ChromaDB 向量搜尋**：將濾除數字後的文字（如：*“Conflict info: instruction is x, disdes is x, delta_ttcp is x... Interaction vehicle driving style: aggressive...”*）轉化為向量。
  * 在刚篩選出的 **top-10 數值候選集範圍內（`filter={'id':{'$in':closest_indices}}`）**，執行餘弦相似度向量搜尋，回傳最優的 `top_k` 個 Few-shot 經驗與 metadata，完成了極具魯棒性的精準檢索。

---

## 4. 冗餘寫入過濾：`addMemory` (Lines 113 - 177)

```python
169:         if self.similar_memory_exist(memory, sce_descrip, action):
170:             print('+++++similar memory exist in dataset, therefore not insert+++++')
171:         else:
175:             memory.add_documents([doc])
```
* 為了防止向量庫內堆積過多雷同的廢數據（導致向量索引膨脹卡頓），在寫入新經驗時呼叫 `similar_memory_exist()`。
* 若在數據庫中已找到極度接近的歷史經驗，且當初做出的決策動作與本次相同，則**拒絕寫入（Not Insert）**；只有遇到新型態的危險場景或決策改變時，才調用 `add_documents` 寫入新條目，實現了資料庫的自我精簡。
