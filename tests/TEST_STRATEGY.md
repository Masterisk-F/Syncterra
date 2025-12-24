# Syncterra テスト戦略 (Test Strategy)

このドキュメントでは、Syncterraプロジェクトにおけるテストの設計方針、構造、および開発ワークフローについて定義します。
私たちは「テストを品質のゲートキーパー」と位置づけ、安心してコード変更が行える状態を維持します。

## 1. テストの階層構造 (Test Pyramid)

テストを以下の3つのレイヤーに分け、実行速度と目的を明確にします。

| レベル | ディレクトリ | 目的 | 特徴 | 実行頻度 |
| :--- | :--- | :--- | :--- | :--- |
| **Unit (単体)** | `tests/unit/` | 関数・クラス単体のロジック検証 | **爆速**。DBやファイルシステムは原則モック化する。 | コード修正のたび (数秒) |
| **Integration (結合)** | `tests/integration/` | DB、ファイル操作、APIの連携検証 | **中速**。実際のSQLiteや一時ファイル(`/tmp`)を使用。 | 機能実装の区切り (数分) |
| **E2E (システム)** | `tests/e2e/` | ユーザー視点での動作検証 | **低速**。ブラウザ操作や実際のAndroid接続。 | リリース前 (数十分〜) |

### ディレクトリ構成
```text
tests/
├── unit/           # ロジック中心のテスト
├── integration/    # DB/FS/API連携テスト
├── e2e/            # (Future) ブラウザ/実機テスト
├── conftest.py     # 共通Fixture (DB接続設定など)
└── TEST_STRATEGY.md # 本ドキュメント
```

## 2. Unit Test と Integration Test の観点

このセクションでは、Unit TestとIntegration Testで **「何を検証するか」「何を検証しないか」** を明確にします。

### 2.1 Unit Test (単体テスト)

**目的**: 個々の関数・クラス・メソッドが、**独立して正しく動作するか**を検証する。

#### ✅ やること
| 観点 | 例 |
|:---|:---|
| **内部ロジックの検証** | パス変換、文字列処理、計算、条件分岐 |
| **エッジケースの網羅** | 空入力、Null、特殊文字、境界値 |
| **例外処理の検証** | エラー時に例外が発生し、適切にハンドリングされるか |
| **戻り値・副作用の検証** | 関数が期待する出力を返すか、引数が正しく処理されるか |

#### ❌ やらないこと
| 観点 | 理由 |
|:---|:---|
| **DBアクセス** | モック化する。実際のDB操作はIntegrationで検証。 |
| **ファイルシステム操作** | モック化する。実際のファイル操作はIntegrationで検証。 |
| **外部プロセス呼び出し** | `subprocess` などはモック化する。 |
| **複数コンポーネントの連携** | 連携はIntegration Testの責務。 |

#### 設計の要点
```python
# 良い例: 外部依存をモックし、ロジック単体をテスト
@patch("ftplib.FTP")
def test_ftp_synchronizer_cp_calls_storbinary(mock_ftp):
    """cpメソッドがFTPのstorbinaryを正しい引数で呼ぶことを検証"""
    sync = FtpSynchronizer(tracks=[], playlists=[], settings={})
    sync.cp("/local/file.mp3", "file.mp3")
    mock_ftp.return_value.storbinary.assert_called_once()
```

---

### 2.2 Integration Test (結合テスト)

**目的**: 複数のコンポーネントが**連携して正しく動作するか**を検証する。

#### ✅ やること
| 観点 | 例 |
|:---|:---|
| **DBとの連携** | ScannerがDBにレコードを正しく保存するか |
| **ファイルシステムとの連携** | 一時ファイルを作成し、Scannerが正しく検出するか |
| **API経由のフロー** | REST APIをリクエストし、DBの状態が変わるか |
| **設定による動作分岐** | sync_mode の値に応じて正しいSynchronizerが使われるか |
| **外部コマンドの発行確認** | `subprocess.run` が正しい引数で呼ばれるか（実行自体はモック可） |

#### ❌ やらないこと
| 観点 | 理由 |
|:---|:---|
| **細かいエッジケース** | Unit Testで網羅済み。Integrationでは主要フローに限定。 |
| **実際の外部サービス** | 本番FTP/SSH/ADBへの接続。ローカルモックサーバーまたはモックを使用。 |
| **UIレンダリング** | フロントエンドのUIテストはE2E層で行う。 |

#### 設計の要点
```python
# 良い例: 実際のDB + モック化したプロセス呼び出しで「フロー」を検証
@pytest.mark.asyncio
async def test_syncer_flow_adb(temp_db, create_settings, patch_db_session):
    """ADBモードで同期すると、adb pushが正しいパスで呼ばれることを検証"""
    await create_settings(sync_mode="adb", sync_dest="/sdcard/Music")
    # ... DBにトラックを追加 ...
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        await SyncService.run_sync()
        
        # 呼び出し検証 (実行はしていないが、連携の正しさを確認)
        assert any("adb" in str(call) for call in mock_run.call_args_list)
```

---

### 2.3 比較まとめ

| 観点 | Unit Test | Integration Test |
|:---|:---|:---|
| **検証対象** | 関数・メソッド単体 | 複数コンポーネントの連携 |
| **データ** | モックデータ | 実DB (インメモリSQLite) |
| **外部依存** | すべてモック | 要所のみモック（DB/FSは実物） |
| **実行速度** | 非常に高速 | やや遅い |
| **テスト数** | 多い（エッジケース網羅） | 少なめ（主要フロー中心） |
| **失敗時の原因特定** | 容易（1箇所に限定） | やや難しい（複数箇所の可能性） |

> **原則**: Unit Testでロジックを網羅し、Integration Testで「組み合わせて動く」ことを保証する。

## 3. 開発ワークフロー (Workflow)

「常にテストが通る状態」を維持するため、以下のサイクルで開発を進めます。

### シナリオ: 既存機能の変更・バグ修正

1.  **現状確認 (Green)**
    *   作業前に全テストを実行し、すべて成功することを確認します。
    *   `uv run pytest` -> **ALL PASS**
2.  **テスト修正/作成 (Red)**
    *   これから実装する仕様に合わせて、**先にテストコードを修正または作成**します。
    *   期待する挙動をテストコードとして定義します。
    *   テスト実行 -> **FAIL** (未実装のため落ちる＝正しい)
3.  **実装 (Green)**
    *   テストが通るようにソースコードを修正します。
    *   テスト実行 -> **PASS**
4.  **回帰テスト (Regression)**
    *   他の機能を壊していないか、全テストを実行します。
    *   `uv run pytest` -> **ALL PASS**
5.  **コミット (Commit)**
    *   全てのテストが通った状態で `git commit` します。

## 4. テストの書き方ガイドライン

### ドキュメントとしてのテスト
テストコード自体が仕様書となるよう、ドキュメンテーション文字列（Docstring）を記述します。

```python
def test_scanner_should_skip_files_without_permission():
    """
    [Scanner] 権限のないファイルはスキップし、エラーログを記録すること。
    
    条件:
    1. 読み取り権限のない .mp3 ファイルが存在する
    2. スキャナーを実行する
    
    期待値:
    1. DBにトラックとして登録されないこと
    2. 処理が中断せず完了すること
    """
    # ... setup ...
    # ... execution ...
    # ... assertion ...
```

### 命名規則
*   ファイル名: `test_*.py`
*   関数名: `test_<対象機能>_<期待する挙動>` または `test_<対象機能>_<条件>`

## 5. 自動化と品質保証 (Automation)

将来的に以下の自動化を導入し、品質維持コストを下げます。

*   **Task Runner**: `uv run ruff check` コマンド等で、Lintを実行。Testは `uv run pytest` で実行。
*   **Pre-commit Hook**: コミット時に自動でテストを実行し、失敗したコードの混入を防ぐ。
*   **Coverage**: 定期的にカバレッジを計測し、テストされていない「死角」を把握する。

---
**合言葉**: "Keep the Build Green" (常にテストが通る状態を保とう)
