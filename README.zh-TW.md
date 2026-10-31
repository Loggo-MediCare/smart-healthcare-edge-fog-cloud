# 智慧醫療 邊緣／霧／雲 部署模擬器

> **僅為模擬，不可用於臨床或病人。** 不連接任何真實裝置、網路或病人資料。所有參數都是假設，列在 `docs/assumptions.md`。

本專案依據《Surgical Robots in Smart Hospitals》第 9 章「AI 融合元宇宙的智慧醫療：部署在霧、邊緣與雲端運算上的 9 種應用」實作。這一章是定性描述，核心主張是表 9.1（雲端、邊緣、霧在延遲、成本、安全性上的比較），以及每個應用該放在哪一層。本專案把這些主張變成可以測試的模型：

* **14 種工作負載**，取自 9.3–9.5 節，例如：遠距病人監測、中風／癲癇偵測、智慧輸液幫浦、義肢、ICU 早期預警、急診檢傷、5G 霧端機器人手術視覺、遠距手術觸覺回饋、VR 認知行為治療、虛擬醫師、病歷分析、疫情預測、基因體分析、模型訓練。
* **三層架構**：每層有運算能力、共用上行頻寬、傳播延遲與抖動、價格、連線中斷，以及資料是否留在院內。
* **五種部署策略**：
  * `all-edge`：全部放邊緣
  * `all-fog`：全部放霧
  * `all-cloud`：全部放雲端
  * `chapter`：照書中的分配
  * `adaptive`：依截止時間選最便宜且可行的層，並對長時間批次工作做霧端准入控制

## 結果（預設假設，60 秒，seed 7；完整表格見 `docs/results.md`）

* **延遲與成本**：單獨比較時符合表 9.1，邊緣 < 霧 < 雲。但這主要是模型的設定本來如此（見 assumptions）。
* **安全性**：書中把霧評為「非常高」，高於邊緣。本模型中邊緣和霧都把原始資料留在院內，每個任務 0 KB 離開醫院，因此無法支持「霧比邊緣更安全」的排名。
* **可用性**：表 9.1 沒有這一項，卻是最能區分三層的指標。連線中斷 15 秒期間，邊緣沒有錯過任何截止時間，霧和雲端則各錯過約 24 %。
* **沒有任何單一層可以全包**：
  * `all-cloud` 幾乎 100 % 錯過攸關安全的截止時間（手術、觸覺、義肢、幫浦）。
  * `all-fog` 錯過約 24 %，因為訓練和基因體工作佔滿了共用的霧端伺服器。
  * `all-edge` 無法執行手術視覺。
* **書中的分配幾乎正確**，攸關安全的錯過率為 0.02 %。`adaptive` 策略達到 0 %，雲端中斷時也維持 0 %。它和書中有三處不同：
  * 遠距手術觸覺回饋和 VR 治療放在裝置端
  * 虛擬醫師和病歷分析放在霧端

  原因是這樣更便宜，而且仍能滿足截止時間。

## 安裝與使用（Windows）

```bash
cd D:\robot\smart-healthcare-edge-fog-cloud
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[test,plot]"
.venv\Scripts\python -m pytest                                   # 14 項測試
.venv\Scripts\python -m edgefog run --policy adaptive            # 各應用的結果表
.venv\Scripts\python -m edgefog compare --cloud-outage 20:35     # 比較所有策略（含雲端中斷）
.venv\Scripts\python -m edgefog report                           # 產生 docs/results.md 和 results.png
```

## 檔案結構

| 路徑 | 用途 |
|---|---|
| `src/edgefog/models.py` | 層級、工作負載、情境、資料範圍 |
| `src/edgefog/catalog.py` | 預設的三層參數與書中的應用 |
| `src/edgefog/sim.py` | 以事件軌跡驅動的模擬器與部署策略 |
| `src/edgefog/metrics.py` | 百分位數、錯過率、成本、離開院內的資料量 |
| `src/edgefog/report.py` | Markdown 報告、表 9.1 檢核與圖表 |
