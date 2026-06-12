# Hermes Gateway Credential Contract Discovery Report

**Milestone:** 7-B.0  
**Status:** Discovery Completed (Revised)  
**Date:** 2026-06-11  

---

## 1. 認證與契約定義 (Authentication Matrix)

針對本機部署與分享模式下的 **OpenAI Compatible Gateway** 代理服務，我們定義了以下兩套不同的認證契約：

| 契約類型 | API Base | 網域與主機限制 | 認證方式 (Authorization Header) | 憑證管理方式與生命週期 | 啟用與審查狀態 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Local OpenAI-Compatible Proxy** | `http://127.0.0.1:8787/v1` | **僅限本機環回 (Exact Loopback):** 必須為 `127.0.0.1` 且通訊埠為 `8787` | **免認證 (No Auth):** 完全不傳送 `Authorization` 標頭，嚴禁加入任何偽造的金鑰。 | **由代理程序獨立託管:** 服務端透過 `google.auth.default()` 及 `refresh()` 於內部自動取得 Google OAuth Access Token。A-RAG 程式端完全無權讀取 GCP 服務帳戶 JSON (ADC)，實施安全職責隔離。 | **已批准 (Approved)**。M7-B 建議採用的預設安全對策。 |
| **Shared Proxy** | 本地入口：`http://127.0.0.1:8788/v1`<br>遠端入口：Cloudflare HTTPS `[REDACTED]` 公開 Origin | **本機或 Cloudflare 公開代理:** 經由 Cloudflare Quick Tunnel 進行遠端轉送。 | **Bearer Token:** 必須攜帶 `Authorization: Bearer ***` 標頭。 | **具過期機制的分享金鑰:** 金鑰載入自 `[REDACTED_ENV]`，其生命週期受限於 `SHARE_EXPIRES_AT`。若時間過期，服務端將主動拒絕請求並回傳 `410 Gone` ("Shared API link has expired")。 | **未批准 (Not Approved)**。本 Milestone 僅保留設計，不作任何程式碼實作。 |

---

## 2. 服務端實際配置與原始證據 (Server-Side Config & Evidence)

經實地安全稽核本機 `C:\TOOL\HarmesAgent\` 下的服務端啟動指令碼與 Python 代理程式，取得以下確鑿證據：

### A. Local OpenAI-Compatible Proxy (本地服務配置)
- **Host 與 Port:** 繫結於 `127.0.0.1:8787`。
- **證據檔案與行號:**
  - `C:\TOOL\HarmesAgent\start-openai-proxy.ps1` 第 10 行：
    ```powershell
    & $python -m uvicorn openai_compatible_proxy:app --host 127.0.0.1 --port 8787
    ```
- **憑證交換與刷新機制:** 服務端內部在載入時使用 `google.auth.default` 與 `refresh`。A-RAG 專案代碼不得嘗試載入憑證。
  - `C:\TOOL\HarmesAgent\openai_compatible_proxy.py` 第 60-68 行：
    ```python
    if _credentials is None:
        _credentials, _ = google.auth.default(scopes=SCOPES)
    _credentials.refresh(google.auth.transport.requests.Request())
    _token = _credentials.token
    ```
- **不對 Client 進行入站認證 (no_auth_localhost):**
  - `C:\TOOL\HarmesAgent\openai_compatible_proxy.py` 第 99-108 行：
    本地 Uvicorn 服務端代理對入站的 Client 請求完全不進行 `Authorization` 校驗，直接使用內部刷新的 GCP Token 轉發至 Google Cloud OpenAI-Compatible AI 上游：
    ```python
    @app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def proxy(path: str, request: Request) -> Response:
        token = _get_access_token()
        ...
        headers["Authorization"] = f"Bearer {token}"
    ```

### B. Shared Proxy (分享代理配置)
- **本地 Port:** 本地預設為 `8788`，或經由 Cloudflare Tunnel 發佈的 HTTPS 公開域名。
- **過期與認證邏輯:**
  - `C:\TOOL\HarmesAgent\share_openai_proxy.py` 第 69-78 行：
    ```python
    authorization = request.headers.get("authorization", "").strip()
    if not authorization.lower().startswith("bearer "):
        return _error(401, "Missing bearer token")
    token = authorization[7:].strip()
    if token != config.api_key:
        return _error(403, "Invalid share API key")
    if datetime.now(UTC) >= config.expires_at:
        return _error(410, "Shared API link has expired")
    ```

---

## 3. Local 模式與 Shared 模式之技術差異

1. **入口網址 (Origin):** 
   - **Local 模式**只接受高強度的安全環回地址 `http://127.0.0.1:8787`；
   - **Shared 模式**除了接受本地 `http://127.0.0.1:8788` 外，更透過 Cloudflare Tunnel 曝露於公開的 HTTPS 域名（`[REDACTED]`）。
2. **認證金鑰有無 (Authorization):**
   - **Local 模式**為 **No Auth** 狀態，對外免除任何入站驗證。Client 端發送請求時不應攜帶、亦不應偽造任何 `Authorization` 標頭；
   - **Shared 模式**則是 **Strict Auth**，Client 必須在 `Authorization` 中提供正確的分享 API 金鑰（`[REDACTED_ENV]`）。
3. **安全邊界與憑證洩漏風險:**
   - **Local 模式**中，GCP 的 `Service Account` / `Application Default Credentials (ADC)` 金鑰檔案（路徑定義於 `C:\secrets\[REDACTED].json`）完全由本機 Proxy 程序在背後載入，A-RAG 測試進程無從接觸此金鑰。
   - **Shared 模式**下，透過 Uvicorn 快取與 Quick Tunnel，外界能以安全的過期分享 Token 進行代理使用。

---

## 4. M7-B 建議配接器 (Adapter) 設計

為落實前述契約，M7-B 應採用無認證環回配接器：

- **配接器名稱:** `NoAuthLoopbackCredentialProvider` (或整合於 Transport 本身之免密碼環回控制)
- **核准邊界與安全性設計:**
  - **嚴格 Origin 檢驗:** 僅允許 Hostname 為 `127.0.0.1` 且 Port 為 `8787` 的 HTTP 連線網址。
  - **拒絕非本機 no-auth:** 若 API Base 檢測到為外部 IP（例如非 `127.0.0.1`、`localhost`）、非 `8787` 通訊埠、或使用 `https` 與任何遠端域名，一律強制拒絕並拋出安全例外、拒絕連線。
  - **免除 Header 發送:** 當 No-Auth Loopback 模式啟動時，Transport 在建立 HTTP Request 時必須**完全省略** (Skip) `Authorization` 標頭的組裝，避免夾帶無效或偽造金鑰。
- **另選方案說明:** `SharedBearerCredentialProvider` 將留作未批准且不予實作的備用機制。在當前 Milestone 絕不對其進行代碼整合。

---

## 5. Gateway Capabilities (網關能力與相容性)

- **支援模型清單 (Supported Models):**
  服務端所支援的模型完全來自服務器環境變數 `VERTEX_MODELS` 的定義（並非只有單一模型）。
  - **預設清單包含:** `GPT5.4`, `google/gemini-3.1-flash-lite-preview`, `google/gemini-3.1-pro-preview`
  - **證據檔案與行號:** `C:\TOOL\HarmesAgent\openai_compatible_proxy.py` 第 17-21 行及 `start-openai-proxy.ps1` 第 7 行。
- **Usage / Request ID / Seed 實際相容性:**
  - **狀態:** `UNRESOLVED`  
  - **說明:** 目前僅有 Client 端的模擬校驗 guard 規範。在尚未正式發起線上實際 API 連線前，服務端底層轉發至 OpenAI OpenEndpoint 後是否能 100% 完整支援 usage 回傳、finish_reason 填寫、Request ID 及 Seed 套用，仍屬未知，必須留待 **M7-C Probe** 單核測試時，由探針進行實測驗證，不在此處提前做推測結論。

---

## 6. 安全事件紀錄 (Security Events)

### 發現持久化分享憑證 (Persistent Shared Credentials Detected)
- **發現事件:** 在服務端工作目錄中，發現了仍處於存活狀態的持久化 Cloudflare Tunnel 分享工作階段，記錄檔案包含：
  - `C:\TOOL\HarmesAgent\runtime\shared-api\share-session.json`
  - `C:\TOOL\HarmesAgent\runtime\shared-api\share-credentials.txt`
- **風險等級:** 高（已記錄公網代理 URL 及 Bearer Token：值均已在分析過程中做 `[REDACTED]` 屏蔽處理）。
- **建議處置對策:** 
  1. 應主動撤銷舊的 share session，停止相關的 Cloudflare 隧道進程。
  2. 立即手動或使用腳本清理、刪除 `C:\TOOL\HarmesAgent\runtime\shared-api\` 底下的 `share-session.json` 與 `share-credentials.txt` 檔案。
  3. **保證原則:** A-RAG repository 中嚴禁拷貝或引入上述任何 Secret 金鑰值。

---

## 7. 剩餘之 UNRESOLVED 項目 (Blockers)

1. **GCP 上游模型的實際 Seed 支援 (`UNRESOLVED`):**  
   OpenAI-Compatible AI 上游端點對 Seed (隨機數種子固定) 的實體支援與表現一致性有待連線驗證。
2. **網關對於 Request ID 的實際透傳相容性 (`UNRESOLVED`):**  
   Google AI Platform OpenAI-Compatible API 對於自訂 OpenAI `x-request-id` 標頭的透傳與接收程度，需待 M7-C Probe 發起後方可由回應標頭稽核。
3. **Usage 數據的完整性 (`UNRESOLVED`):**  
   是否所有 upstream models 皆能完美回傳 token 計數結構，需在探針執行後完成解析。
