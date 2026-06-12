# Milestone 3 設計計畫：安全隔離、Runtime 與 Evaluator

- **文件日期**：2026-06-11
- **狀態**：PROPOSED (已規劃，等待核准，尚未實作)
- **版本目標**：
  - **M3.0**：Result Schema Amendment
  - **M3.1**：Runtime、安全隔離與 Patch Engine
  - **M3.2**：Evaluator 與多輪修復流程

---

## 系統資料流圖 (Data Flow Diagram)

```text
                               +-------------------------------------------+
                               |             experiments/tasks.json        |
                               +---------------------+---------------------+
                                                     |
                                                     v (Task metadata & max_repair_rounds)
+------------------------+       +-------------------+-----------+       +-----------------------------+
|     SNAPSHOT.json      +------>+     Workspace Creator         +------>+    Clean Run Workspace      |
+------------------------+       +-------------------+-----------+       |    (tempfile.TempDir)       |
                                                     |                   +--------------+--------------+
                                                     | (Verify SHA-256)                 |
                                                     |                                  | (1. Apply initial_patch)
                                                     v                                  v
+------------------------+       +-------------------+-----------+       +--------------+--------------+
|   Agent Initial Patch  +------>+     Unified Diff Validator    +------>+    Patch Applier Engine     |
+------------------------+       +-------------------+-----------+       +--------------+--------------+
                                                     |                                  |
                                                     | (Strict file and traversal checks) | (2. Run Public / Hidden)
                                                     v                                  v
+------------------------+       +-------------------+-----------+       +--------------+--------------+
| Hidden Test            |------>+   Secure Test Runner (JUnit)  +------>+    Isolated Subprocess       |
| (Outside Workspace CWD)|       +-------------------+-----------+       |    (PYTHONDONTWRITEBYTE1)   |
+------------------------+                   |                           +--------------+--------------+
                                             | (Generate HiddenSummary)                 |
                                             v                                          | (Capture JUnit XML & metrics)
+------------------------+       +-----------+-----------+                              |
| Sanitized Feedback     +<------+    Evaluator Engine   +<-----------------------------+
| (Under Public Policy)  |       +-----------+-----------+
+------------------------+                   |
                                             v (Validate via Draft 2020-12 Result Schema)
                                 +-----------+-----------+
                                 |  Result Schema Log    |
                                 +-----------------------+
```

---

## 一、 預定實作模組與公開介面設計 (Public Interfaces & Types)

### 1.1 Workspace 模組 (`experiments/runtime/workspace.py` - M3.1)

負責動態建立獨立、拋棄式、完全與主 Repo 隔離的實體 Workspace，進行三階段完整性校驗。

```python
from typing import Dict, Any, List
import tempfile
from pathlib import Path

class WorkspaceError(Exception): pass
class CleanupError(WorkspaceError): pass

class WorkspaceManager:
    """
    管理每個 Run_ID 專屬的物理沙盒生命週期，執行三階段不變量驗證。
    """
    def __init__(self, run_id: str, task_id: str, snapshot_path: str = "student_system/SNAPSHOT.json"):
        self.run_id: str = run_id
        self.task_id: str = task_id
        self.snapshot_path: Path = Path(snapshot_path).resolve()
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self.workspace_path: Path | None = None

    def create(self) -> Path:
        """
        1. 【階段 A：建立前驗證原始快照】：讀取並比對真實 student_system 檔案之 SHA-256 是否與 snapshot_path 登載完全一致。
        2. 建立系統暫存目錄（tempfile.TemporaryDirectory()）。
        3. 【階段 B：複製後、套用補丁前校驗】：
           - 將 SNAPSHOT 追蹤的起點檔案複製到沙盒中（嚴格排除 __pycache__、.pytest_cache、*.pyc）。
           - 排除所有隱藏測試、參考補丁、results 或其他 run 專屬 workspace。
           - 複製完成後，對沙盒內之複本再次核對 SHA-256，確認無拷貝損毀。
        4. 物理隔離限制：確認 workspace_path 絕對不加入 sys.path 中，防範記憶體級 runtime 污染。
        :return: 沙盒的 Path 物件 (絕對路徑)
        :raises WorkspaceError: 當初始化失敗、快照不符或驗證失敗時拋出。
        """
        pass

    def verify_post_patch_integrity(self, files_to_modify: List[str]) -> bool:
        """
        【階段 C：補丁後只允許授權變更】：
        - 檢查沙盒內所有檔案，除了名列於 files_to_modify 中的檔案可以發生變更外，
        - 其餘所有 SNAPSHOT 追蹤的檔案其 SHA-256 必須保持絕對不變。
        - 斷言此過程中沒有任何新增檔案、刪除檔案、或非授權檔案被修改。
        :raises WorkspaceError: 當偵測到越權增刪、非預期修改時。
        """
        pass

    def cleanup(self) -> None:
        """
        1. 物理移除暫存沙盒目錄。
        2. 鎖定防禦：若在 Windows 上移除失敗，絕不靜默忽略，必須拋出 CleanupError 阻斷測試。
        """
        pass
```

### 1.2 Patch Validator & Applier (`experiments/runtime/patching.py` - M3.1)

自製 Unified Diff 解析器，安全過濾格式與防禦命令注入，禁止使用系統 shell。

```python
from pathlib import Path
from typing import List

class PatchError(Exception): pass
class InvalidPatchError(PatchError): pass    # 補丁語法不正確、越權修改不允許的檔案、含有 path traversal 等
class PatchApplyError(PatchError): pass      # 補丁格式正確，但因衝突或基底程式碼不合而無法順利套用

class PatchEngine:
    """
    Unified Diff 補丁安全校驗與物理套用引擎（100% Python 原生解析，嚴禁調用 shell）。
    """
    @staticmethod
    def validate_patch(patch_content: str, files_to_modify: List[str]) -> None:
        """
        嚴格分析 Unified Diff 內容，若偵測到以下狀況必須拋出 InvalidPatchError：
        - 檔案路徑包含絕對路徑、含有 '..' 的路徑穿越（Path Traversal）。
        - 提及 '/dev/null'（禁止新增或刪除檔案）、建立檔案（create）或刪除檔案（delete）。
        - 補丁企圖修改非 files_to_modify 指定之檔案。
        - 包含重命名（rename）或二進位差異（binary diff）。
        - 包含重複 section、malformed hunk 格式、行數與 context mismatch（內容不匹配）。
        - 包含潛在之 git apply / patch shell 命令注入字元。
        """
        pass

    @staticmethod
    def apply_patch(workspace_path: Path, patch_content: str) -> None:
        """
        1. 在指定隔離工作區內套用 Unified Diff。
        2. 原生 Python 解析套用，不得呼叫 patch 或 git apply 等系統 shell。
        :raises PatchApplyError: 當 Hunk 衝突、基底代碼不匹配或套用失敗時。
        """
        pass
```

### 1.3 Test Runner 模組 (`experiments/runtime/test_runner.py` - M3.1)

將 PublicTestResult 與 HiddenTestSummary 分離，透過 JUnit XML 解析統計，清空 PYTHONPATH 並以絕對路徑在工作區外部執行隱藏測試。

```python
from pathlib import Path
from typing import Dict, Any, List

class PublicTestResult:
    """
    公開測試結果的詳細資料結構。
    """
    def __init__(self, passed: bool, passed_tests: List[str], failed_tests: List[str],
                 stdout: str, stderr: str, traceback: str, duration_seconds: float, timeout_occurred: bool,
                 total_count: int = 0, skipped_count: int = 0, collection_error: str = "", runner_error: bool = False):
        self.passed: bool = passed
        self.passed_tests: List[str] = passed_tests
        self.failed_tests: List[str] = failed_tests
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.traceback: str = traceback
        self.duration_seconds: float = duration_seconds
        self.timeout_occurred: bool = timeout_occurred
        self.total_count: int = total_count
        self.skipped_count: int = skipped_count
        self.collection_error: str = collection_error
        self.runner_error: bool = runner_error

class HiddenTestSummary:
    """
    隱藏測試摘要：極度去敏，僅保留計數與超時指標，絕不洩漏測試細節。
    """
    def __init__(self, passed_count: int, total_count: int, duration_seconds: float, timeout_occurred: bool, runner_error: bool = False):
        self.passed_count: int = passed_count
        self.total_count: int = total_count
        self.duration_seconds: float = duration_seconds
        self.timeout_occurred: bool = timeout_occurred
        self.runner_error: bool = runner_error
        # 嚴格禁止：不得包含任何 stdout, stderr, traceback, 測試名稱, 或 hidden 測試檔案路徑

class SecureTestRunner:
    """
    安全子進程測試執行器，透過 JUnit XML 收集數據，防止殘留。
    """
    def __init__(self, workspace_path: Path, approved_hidden_root: Path, timeout_seconds: float = 30.0):
        self.workspace_path: Path = workspace_path
        self.approved_hidden_root: Path = approved_hidden_root
        self.timeout_seconds: float = timeout_seconds

    def run_public_tests(self, test_paths: List[str]) -> PublicTestResult:
        """
        1. 建立 Subprocess，CWD=workspace_path，--rootdir=workspace_path。
        2. 環境變數：`PYTHONDONTWRITEBYTECODE=1`，並清空 `PYTHONPATH` 確保無法向外 import 污染。
        3. 透過 `--junitxml` 輸出到指定臨時路徑，解析完畢後立即徹底刪除 XML 檔案。
        """
        pass

    def run_hidden_tests(self, hidden_test_absolute_paths: List[str]) -> HiddenTestSummary:
        """
        1. 隱藏測試檔案絕對位於 code workspace 之外（主專案 evaluation/hidden_tests/ 下的絕對路徑）。
        2. 建立 Subprocess，CWD=workspace_path，--rootdir=workspace_path。
        3. 環境變數：`PYTHONDONTWRITEBYTECODE=1`，清空 `PYTHONPATH`。
        4. 執行命令指向外部絕對路徑（例如：`python -m pytest /absolute/path/to/hidden_test_t01.py`）。
        5. 使用獨立的 evaluator-owned temp dir 來放置 JUnit XML，讀取 passed/total 後立即刪除 XML。
        6. 只封裝為 HiddenTestSummary，任何 stdout/stderr/traceback 絕不洩漏。
        """
        pass

    @staticmethod
    def sanitize_feedback(public_result: PublicTestResult, policy_mapping: Dict[str, Any]) -> str:
        """
        根據 tasks.json 中的 public_feedback_policy Mapping 進行公開測試去敏。
        policy_mapping 必須包含：
        - include_stdout (bool)
        - include_stderr (bool)
        - include_traceback (bool)
        - max_chars (int)
        
        * 警告：HiddenTestSummary 絕對不准、也無法傳入本 sanitize_feedback 函式，防止程序漏洞導致意外洩漏！
        """
        pass
```

### 1.4 Path Guards 模組 (`experiments/runtime/guards.py` - M3.1)

處理 Windows 路徑與大小寫正規化，使用 `Path.is_relative_to` 防範 `sibling-prefix` 逃逸，並具備 Symlink 權限不足時的 skip 安全備案。

```python
from pathlib import Path

class GuardError(Exception): pass
class PathEscapeError(GuardError): pass

class SecurityGuards:
    """
    嚴格檢測路徑越權、大小寫正規化與 Symlink/Junction 逃逸。
    """
    @staticmethod
    def assert_safe_path(target_path: Path, approved_base: Path) -> None:
        """
        1. 將 target_path 與 approved_base 均 resolve 到真實物理路徑。
        2. 嚴防 sibling-prefix 逃逸漏洞：
           - 漏洞描述：若 approved_base 為 Path("C:/base")，而 target_path 為 Path("C:/base2/file.txt")。
           - 若僅使用字串 startswith 判斷：`str(target_path).startswith(str(approved_base))` 會回傳 True，導致路徑逃逸到同級目錄。
           - 解決對策：必須使用 Python 3.9+ 的 `Path.is_relative_to` 判斷。
           - 實例：`assert target_path.is_relative_to(approved_base)`。
        3. Windows 正規化：將反斜線統一置換為正斜線 `/`，且統一轉換為小寫進行字串核對。
        :raises PathEscapeError: 偵測到逃逸企圖時。
        """
        pass
```

### 1.5 Evaluator 模組 (`experiments/evaluation/evaluator.py` - M3.2)

修正重新定義之 Pass 1 與 Pass 2 的不變量運作流程，移除內部的 Starter Red 測試。

```python
from pathlib import Path
from typing import Dict, Any, Sequence
from experiments.runtime.workspace import WorkspaceManager
from experiments.runtime.test_runner import SecureTestRunner

class Evaluator:
    """
    實驗評估核心：精準控制 Pass 1 與 Pass 2 多輪修復評估（M3.2）。
    """
    def __init__(self, task_config_path: str = "experiments/tasks.json"):
        self.task_config_path: Path = Path(task_config_path).resolve()
        self.tasks: Dict[str, Any] = {}

    def evaluate_task_with_deterministic_patch(self, task_id: str, 
                                               initial_patch: str | None, 
                                               repair_patches: Sequence[str] = (),
                                               max_repair_rounds: int = 2) -> Dict[str, Any]:
        """
        1. 從 tasks.json 中取得題目參數（files_to_modify, public_test_paths 等）。
        2. 建立 WorkspaceManager 並呼叫 create()。
        3. 【移除內部 Starter Red Verification】：
           - 為了維持職責單一與核心執行迴圈的潔淨，正式 Evaluator 內不包含 Starter Red 驗證程式碼。
           - Starter Red 驗證被移出，作為前置環境不變量核對或在單元測試斷言中獨立處理。
        4. 【Pass 1（套用 initial_patch 階段）】：
           - 若存在 initial_patch，經由 PatchEngine 驗證並套用至沙盒中。
           - 使用 WorkspaceManager.verify_post_patch_integrity 驗證只有 files_to_modify 被修改。
           - 執行測試，將此時得到的結果記錄為：`pass1_public` 與 `pass1_hidden`。
        5. 【修復與 Pass 2（多輪修復階段）】：
           - 若 `pass1_public` 失敗且存在 `repair_patches`（Sequence[str]）：
             - 依序遍歷修復補丁，上限為 max_repair_rounds。
             - 每套用一個 `repair_patch`，必須再次通過只修改 files_to_modify 的防禦核對。
             - 執行測試。若測試通過或達到 max_repair_rounds，則停止。
           - 記錄最後測試結果為：`final_public` 與 `final_hidden`。
           - 統計修復輪數：實際進行的修復補丁套用與執行次數（`repair_rounds` 介於 0 到 max_repair_rounds 之間）。
        
        * 確定性正例特例 (Reference Patch Flow)：
          當使用 Reference Patch 作為 initial_patch 傳入時，由於直接滿分通過，故預期：
          - `pass1_public = True`
          - `pass1_hidden = True`
          - `repair_rounds = 0` (完全不需要後續修復流程)
          
        * 確定性反例與修復流：
          當使用 Incomplete Patch（不完整補丁）作為 initial_patch 傳入時：
          - 預期：套用後 `pass1_public = False`
          - 接著傳入正確的修正 `repair_patches` 進行修補，預期最後：`final_public = True` 且 `final_hidden = True`。
          
        6. 匯出完全符合 Result Schema 的報表，並對其進行 Schema 驗證。
        7. 釋放沙盒並自動清除。
        :return: 驗證後的 Result 報表字典。
        """
        pass
```

### 1.6 Metrics 模組 (`experiments/evaluation/metrics.py` - M3.2)

分離 infra_error 與模型輸出錯誤，精確定義 valid_run。

```python
class MetricsCollector:
    """
    指標過濾、Valid Run 判定與錯誤對照。
    """
    @staticmethod
    def classify_error(exception: Exception) -> tuple[str, bool, str]:
        """
        將例外精密對照到 Result Schema 的對應欄位。
        
        * 判定 valid_run == !infra_error。
        * 模型與大腦輸出之錯誤，不屬於系統基礎設施崩潰（infra_error=False）：
          - InvalidPatchError -> error_type='invalid_patch', infra_error=False, stop_reason='repair_limit'
          - PatchApplyError -> error_type='patch_apply_error', infra_error=False, stop_reason='repair_limit'
          - EmptyResponseError -> error_type='empty_response', infra_error=False, stop_reason='repair_limit'
          
        * 系統級與測試期基礎設施超時或崩潰（infra_error=True）：
          - subprocess.TimeoutExpired -> error_type='test_timeout', infra_error=True, stop_reason='infra_error'
          - TestRunnerError / subprocess.SubprocessError -> error_type='runner_error', infra_error=True, stop_reason='infra_error'
          
        :return: (error_type, infra_error, stop_reason)
        """
        pass
```

---

## 二、 例外與錯誤型別 Enum 對應表 (Exception to Schema Enum Mapping)

為保證 evaluator 生產的 `result.json` 與 M1 訂立的契約無縫接軌，Python 例外精密對照路由表修正如下：

| Python 發生之例外狀況 / 狀態 | `infra_error` | `valid_run` | `error_type` Enum | `stop_reason` Enum | 說明 |
| :--- | :---: | :---: | :--- | :--- | :--- |
| **無任何錯誤且測試全數通過** | `False` | `True` | `none` | `public_pass` | 正常運作且完全正確 |
| **修復輪數達到設定上限 (2輪)** | `False` | `True` | `none` | `repair_limit` | 正常套用但未能通過全部測試 |
| **靜態 Patch 格式非法或越權** | `False` | `True` | `invalid_patch` | `repair_limit` | **非 infra_error**，stop_reason 非 infra_error，代表大腦產生不合格代碼 |
| **Patch 衝突、衝突無法 merge** | `False` | `True` | `patch_apply_error` | `repair_limit` | **非 infra_error**，stop_reason 非 infra_error，代表大腦產生不合格代碼 |
| **大腦生成 API 內容完全為空** | `False` | `True` | `empty_response` | `repair_limit` | **非 infra_error**，stop_reason 非 infra_error，代表大腦產生不合格代碼 |
| **pytest 子進程執行超時** | `True` | `False` | `test_timeout` | `infra_error` | **為 infra_error**，因環境執行掛死 |
| **Runner 環境遺失、核心崩潰** | `True` | `False` | `runner_error` | `infra_error` | **為 infra_error**，因基礎設施不可用 |
| **其他未預期非受控例外** | `True` | `False` | `unknown` | `infra_error` | **為 infra_error**，未知系統錯誤 |

---

## 三、 TDD 執行順序與測試設計 (TDD Sequence & Test Assertions)

### 3.1 測試套件詳細斷言規劃 (Test Assertions)

#### 3.1.1 隔離與 Workspace 測試 (TDD Step 1)
* **測試名稱**：`tests/runtime/test_workspace_isolation.py`
* **測項與具體斷言**：
  1. `test_workspace_snapshot_validation_no_corruption_allowed`:
     - **步驟**：建立複本時，**必須操作 `tmp_path` 中的學員系統複本，絕對不允許修改本機正式的 `student_system` 檔案**。修改複本中其中一個被 snapshot 追蹤的檔案。呼叫 `create()`。
     - **斷言**：預期拋出 `WorkspaceError`。
  2. `test_workspace_integrity_post_patch`:
     - **步驟**：建立沙盒，模擬在沙盒內新增、刪除或修改非 `files_to_modify` 指定之檔案，呼叫 `verify_post_patch_integrity`。
     - **斷言**：預期拋出 `WorkspaceError` 阻斷。

#### 3.1.2 補丁語法與 Unified Diff Parser 測試 (TDD Step 2)
* **測試名稱**：`tests/runtime/test_patch_engine.py`
* **測項與具體斷言**：
  - 補丁解析器對非法補丁的拒絕測試。
  1. `test_reject_absolute_path_and_traversal` -> 補丁包含 `C:\`、`/etc/` 或 `..` -> `assert raises InvalidPatchError`
  2. `test_reject_dev_null_and_creation_deletion` -> 補丁包含 `/dev/null` 企圖新增/刪除檔案 -> `assert raises InvalidPatchError`
  3. `test_reject_rename_and_binary_diff` -> 補丁包含重命名或二進位格式 -> `assert raises InvalidPatchError`
  4. `test_reject_mismatched_hunk_and_context` -> 補丁內容與基底檔案文字不匹配、行數有誤 -> `assert raises PatchApplyError` 或 `InvalidPatchError`

#### 3.1.3 測試執行、去敏與程序樹超時終止測試 (TDD Step 3)
* **測試名稱**：`tests/leakage/test_leakage_prevent.py`
* **測項與具體斷言**：
  1. `test_import_source_comes_from_workspace_only`:
     - **步驟**：在隔離沙盒內執行 hidden test。
     - **斷言**：在測試中讀取被載入學員模組（例如 `student_system.src.student`）之 `__file__` 屬性，**斷言其絕對路徑必須位於沙盒 `workspace_path` 之內，絕對不允許指向 root 本地主模組路徑**。
  2. `test_junit_xml_generation_and_immediate_removal`:
     - **步驟**：執行測試。
     - **斷言**：確認測試數據來源為 `--junitxml`，且執行完畢後，不論測試成功或失敗，放置 JUnit XML 的臨時檔案都**已 100% 被物理移除**，不殘留敏感測試名稱。
  3. `test_subprocess_timeout_kills_only_target_tree`:
     - **步驟**：在測試沙盒中啟動一個包含 `time.sleep(100)` 的掛死測試，觸發超時（1秒）。
     - **斷言**：
       - `assert raises TimeoutExpired`。
       - 檢查系統進程清單，確認只有該特定掛死子進程（被捕獲的 PID 及其子進程樹）被精確終止，**當前正在執行 pytest 的主 Python 進程與其他無關 Python 程序完好無損，絕對不得被廣泛終止。**
  4. `test_symlink_creation_permission_fallback_skip`:
     - **步驟**：測試中企圖建立 symlink 做路徑逃逸測試。
     - **說明**：若在 Windows 下無管理員權限建立 symlink 失敗（拋出 `OSError` 或 `PermissionError`），**自動呼叫 `pytest.skip("Windows non-admin symlink not supported")` 跳過該創立測試。**
     - **不依賴權限的比對測試**：同時保留不依賴權限的 resolved-path 逃逸測試，直接對 `SecurityGuards.assert_safe_path` 輸入帶有非法逃逸路徑、Junction（如 `C:\base2` 與基準 `C:\base` 對照）或大小寫錯亂路徑的 `Path` 參數，核對其是否能正確拋出 `PathEscapeError`，確保安全邏輯在任何權限環境下皆有 100% 覆蓋率。

---

## 四、 Milestone 3 核心 Blockers 與 Schema 修正修訂提案 (M3 Blockers & Schema Amendment Proposal)

### 4.1 核心 Blockers 分析（已解決）
在原始 `result.schema.json` 的嚴格 Draft 2020-12 契約中，人工評分欄位如 `requirement_score`、`quality_score`、`api_correct`、`hallucinated_api` 被列為 **required**（必填欄位）且只接受整數型別。
- 然而，當自動化評估器剛完成執行、人工評分狀態 (`manual_review_status`) 尚處於 `"pending"` 時，系統是**無法、也不應該虛構任何人工評分值**填入 result 的。
- **這在 M3.0 中已透過 Schema Amendment 修正。當前已完成 Schema 與對應測試的修訂，解決了此 Blocker。**

### 4.2 Schema Amendment 實作設計
已在 M3.0 實作中正式導入以下 `if-then-else` 狀態條件約束：

1. **基本方案**：利用 JSON Schema Draft 2020-12 的 `if-then-else` 語法進行狀態條件約束。
2. **核心條件約束**：
   - 當評分狀態為 **pending** 時，人工評分欄位允許為 **null**（即 `pending + null` 組合）。
   - 當評分狀態為 **reviewed** 或 **disputed** 時，人工評分欄位必須為 **integer** 數值（即 `reviewed + integer` 組合）。
3. **條件合約語法範例**：
   ```json
   {
     "properties": {
       "manual_review_status": { "type": "string", "enum": ["pending", "reviewed", "disputed"] },
       "requirement_score": { "type": ["integer", "null"], "minimum": 0, "maximum": 2 },
       "quality_score": { "type": ["integer", "null"], "minimum": 1, "maximum": 5 },
       "api_correct": { "type": ["integer", "null"], "minimum": 0, "maximum": 1 },
       "hallucinated_api": { "type": ["integer", "null"], "minimum": 0, "maximum": 1 }
     },
     "if": {
       "properties": {
         "manual_review_status": { "const": "pending" }
       }
     },
     "then": {
       "properties": {
         "requirement_score": { "type": "null" },
         "quality_score": { "type": "null" },
         "api_correct": { "type": "null" },
         "hallucinated_api": { "type": "null" }
       }
     },
     "else": {
       "properties": {
         "requirement_score": { "type": "integer" },
         "quality_score": { "type": "integer" },
         "api_correct": { "type": "integer" },
         "hallucinated_api": { "type": "integer" }
       }
     }
   }
   ```

---

## 五、 M3 驗收項目檢查清單 (Checkbox Tracker)

以下為 Milestone 3 預定驗收必須達成的核對指標：

- [ ] **Workspace 獨立多階段複製與完整性校驗**：
  - 建立前驗證原始 snapshot。
  - 複製後、patch 前完整驗證。
  - patch 後只允許 `files_to_modify` 發生變更，禁止增刪其他檔案。
- [ ] **物理隔離與絕對路徑執行**：
  - Workspace 目錄不加入 `sys.path`。
  - `PYTHONPATH` 清空。
  - pytest 運作使用 `cwd=workspace` 與 `--rootdir=workspace`。
  - 隱藏測試檔案絕對位於 code workspace 之外，並以 evaluator-only 的外部絕對路徑執行。
- [ ] **被導入模組實體檢驗**：
  - 測試斷言隱藏測試中被載入學員模組的 `__file__` 必須絕對位於 workspace 暫存沙盒內。
- [ ] **測試結果與摘要分離**：
  - `PublicTestResult` 與 `HiddenTestSummary` 分離。
  - `HiddenTestSummary` 僅保留通過數、總數與超時指標，絕不含有 stdout/stderr/traceback 或敏感檔名路徑。
- [ ] **Public Feedback 映射配置**：
  - `sanitize_feedback` 接受 tasks.json 定義之 `include_stdout`、`include_stderr`、`include_traceback` 及 `max_chars` 限制，且 Hidden summary 絕對不准傳入 sanitizer。
- [ ] **JUnit XML 統計解析與除淨**：
  - 不解析人类可讀 stdout。
  - XML 檔案必須放置在獨立 evaluator-owned temp dir，解析後在 python 記憶體中立即物理刪除。
- [ ] **精準超時進程樹終止**：
  - 超時掛死時，只精確終止該特定捕獲的子程序 PID 及其 child 進程樹，不得廣泛誤殺 Python 系統程序。
- [ ] **Symlink 權限不足 skip 與 resolved 逃逸比對驗證**：
  - 測試在 Windows 下 symlink 權限不足時自動 skip，且保留不依賴 symlink 的 resolved-path 逃逸字串比對，防範 Windows 大小寫與反斜線逃逸。
- [ ] **重新定義的 Pass 1 與 Pass 2 驗收**：
  - Starter Red 狀態只作為 pre-execution 驗證，不計入 Pass 1。
  - Pass 1 屬於 `initial_patch` 後的成果。
  - Reference patch 作為 `initial_patch` 預期 `pass1_public=True` 且 `repair_rounds=0`。
  - 獨立 incomplete patch 測試 Pass 1 失敗、repair 後 final 成功之確定性驗核流程。
- [ ] **Valid Run 不變量與錯誤對照**：
  - `valid_run == !infra_error`
  - 區分 `invalid_patch`, `patch_apply_error`, `empty_response` 等大腦代碼不合規（`infra_error=False`）與測試超時等系統故障（`infra_error=True`）。
