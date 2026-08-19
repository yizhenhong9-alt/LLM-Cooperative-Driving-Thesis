# CoDrivingLLM `highway_env/__init__.py` 逐行詳細代碼解析

本文件解讀 `highway_env` 套件的初始化入口檔 `__init__.py`。

---

## 1. 完整程式碼與逐行解析

```python
1: # Hide pygame support prompt
2: import os
3: os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
4: # Import the envs module so that envs register themselves
5: import highway_env.envs
6: 
```

* **第 2-3 行**：導入 `os` 庫，並在環境變數中寫入 `PYGAME_HIDE_SUPPORT_PROMPT = '1'`。
  * **作用**：當導入 Pygame 庫時，終端機會預設印出其官方廣告和版本支援訊息（例如：*`Hello from the pygame community...`*）。此設定能徹底關閉這個提示，使終端日誌乾淨整潔。
* **第 5 行**：導入 `highway_env.envs` 模組。
  * **作用**：當其它檔案首次導入 `import highway_env` 時，會觸發本檔執行，進而鏈式調用 `highway_env.envs` 下的 `__init__.py`。這會觸發 `highway_env/envs/` 下所有自定義仿真場景（如直行、十字路口、匝道合流）的 `register()` 註冊碼，確保模擬器環境向 OpenAI Gym 的註冊成功。
