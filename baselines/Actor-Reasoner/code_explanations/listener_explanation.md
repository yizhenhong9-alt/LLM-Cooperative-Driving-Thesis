# Actor-Reasoner `listener.py` 逐行詳細代碼解析

本文件解讀 `Actor-Reasoner/` 專案下的語音控制與即時聽寫語音辨識模組 `listener.py`。它負責建立一個後台語音監聽線程，為乘客或外部行駛意圖提供語音交互支援。

---

## 1. 完整程式碼與逐行解析

```python
1: import speech_recognition as sr
2: 
3: class ContinuousSpeechToText:
4:     def __init__(self):
5:         self.recognizer = sr.Recognizer()
6:         self.microphone = sr.Microphone()
```
* **第 1-6 行**：導入 `speech_recognition` 庫（Python 經典語音聽寫套件）。初始化語音辨識器實例 `self.recognizer`，並綁定系統默認麥克風 `self.microphone` 作為音訊輸入源。

```python
8:     def listen_and_convert(self):
...
15:         try:
16:             with self.microphone as source:
17:                 self.recognizer.adjust_for_ambient_noise(source)  # 自動調節環境噪音
18:                 print("Ambient noise adjustment completed. Start listening...")
```
* **第 8-18 行**：開啟監聽主程序。調用 `adjust_for_ambient_noise` 音訊調節函式。它會自動錄製約 1 秒的環境音背景雜訊，設定音量振幅動態閾值，避免環境風噪、電腦風扇等白噪音干擾語音判定。

```python
20:                 while True:
21:                     print("Waiting for speech input...")
22:                     # 阻塞監聽，直到檢測到人聲說話
23:                     audio = self.recognizer.listen(source)
24:                     print("Speech input detected, starting recognition...")
```
* **第 20-24 行**：進入無限監聽循環。呼叫 **`self.recognizer.listen(source)`**。此函式會保持阻塞掛起狀態，直到麥克風的音頻強度超出剛才設定的噪音閾值，並在人聲說完停止後，完成音訊錄製打包為 `audio` 對象。

```python
26:                     try:
27:                         # 調用 Google Web Speech API 進行在線聽寫轉化
28:                         text = self.recognizer.recognize_google(audio, language="en-US")
29:                         print(f"Recognition result: {text}")
30:                         return text
```
* **第 26-30 行**：調用 GoogleSpeechAPI 的免費在線聽寫接口 `recognize_google()`。指定語言為美式英語 `"en-US"`。該接口會快速返回聽寫得到的文本字符串（如 `"speed up"` 或 `"yield to the left car"`），並跳出循環將其返回。

```python
31:                     except sr.UnknownValueError:
32:                         print("Could not understand the speech. Please try again.")
33:                     except sr.RequestError as e:
34:                         print(f"Speech recognition service error: {e}")
```
* **第 31-42 行**：捕捉語音辨識異常：
  * `UnknownValueError`：錄製的聲音太糊或非人類語言，無法解析。
  * `RequestError`：網路斷開或 Google API 連接失敗，回傳錯誤代碼。
