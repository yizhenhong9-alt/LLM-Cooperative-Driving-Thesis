# CoDrivingLLM `llm_controller/memory.py` 逐行詳細代碼解析

本文件解讀 `llm_controller` 目錄下的駕駛經驗數據庫接口檔 `memory.py`。它負責封裝 ChromaDB 向量數據庫，為大模型提供基於語意相似度檢索（Semantic Similarity Search）的 Few-shot 駕駛先驗經驗。

---

## 1. Ollama 本地向量嵌入服務：`OllamaLocalEmbeddings` (Lines 15 - 45)

這是原作者為 Ollama（開源大模型運作架構）自定義的嵌入（Embedding）類別，繼承自 LangChain 的 `Embeddings` 基底：

```python
15: class OllamaLocalEmbeddings(Embeddings):
16:     def __init__(self, base_url: str, model: str):
17:         self.base_url = base_url.replace("/v1", "").rstrip("/")
18:         self.model = model
```
* **作用**：當使用 Ollama 開源模型（而非收費的 OpenAI API）時，需要將 prompt 文本轉化為 1024 或 4096 維的浮點數向量。
* **向量嵌入求解 (Lines 23-44)**：
  發送 POST 請求至本地 Ollama 的 `api/embeddings`（新版 API 為 `api/embed`）。將文字內容 `text` 傳入，獲取回傳的特徵向量並返回。如果本地載入失敗，會拋出 RuntimeError。

---

## 2. 駕駛經驗數據庫管理器：`DrivingMemory` (Lines 46 - 142)

此類別是駕駛歷史經驗讀寫的核心接口：

```python
46: class DrivingMemory:
47:     def __init__(self, env) -> None:
...
55:         db_path = './db/' + str(env.spec.id)
56:         self.scenario_memory = Chroma(
57:             embedding_function=self.embedding,
58:             persist_directory=db_path
59:         )
```
* **數據庫實例化**：根據當前的仿真場景 ID（如 `highway-v0`），在根目錄 `./db/` 下建立對應的持久化向量文件夾。加載 LangChain Chroma 引擎。
* **語意相似經驗檢索 (Retrieve - Lines 64-70)**：
  ```python
  def retrieveMemory(self, query_scenario, top_k=5):
      similarity_results = self.scenario_memory.similarity_search_with_score(query_scenario, k=top_k)
      ...
      return fewshot_results
  ```
  * **解讀**：自駕車在當前 Step 遇到危險時，將當前的「危險描述文本」作為 `query_scenario`。ChromaDB 會在背景將此文本轉化為向量，與數據庫中歷史儲存的所有經驗進行餘弦相似度計算，篩選出最相似的 `top_k` 個駕駛經驗，提取出其 metadata 並回傳給決策提示詞工程。
* **保存新經驗 (Add - Lines 102-110)**：
  ```python
  def addMemory(self, sce_descrip, human_question, negotiation, action, comments):
      doc = Document(page_content=sce_descrip, metadata={"human_question": human_question, ...})
      self.scenario_memory.add_documents([doc])
  ```
  * 將危險場景描述（`sce_descrip`）作為向量檢索的 key 文本，將大模型最終執行的動作（`action`）與安全性評價（`comments`，如 `'good decision'` 或 `'bad decision'`) 以 metadata 形式綁定保存。
* **合併跨場景數據庫 (Combine - Lines 123-141)**：
  `combineMemory` 遍歷另一個 ChromaDB 資料庫中的所有條目向量。若是當前資料庫中不存在（無重複），則調用 `_collection.add` 合併。這方便了在 Highway、Merge 和 Intersection 不同地圖訓練得到的駕駛記憶進行跨地圖融合。
