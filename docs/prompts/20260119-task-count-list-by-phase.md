# task_count list_by_phaseコマンドの実装

## 概要

フェーズごとのタスク数をCSV形式で出力する `task_count list_by_phase` コマンドを新規作成しました。
プロジェクトの現在のタスクの状態を一目で把握するためのコマンドです。

## 実装内容

### 新規作成ファイル

- `annofabcli/task_count/__init__.py` - task_countパッケージ
- `annofabcli/task_count/subcommand_task_count.py` - サブコマンド登録
- `annofabcli/task_count/list_by_phase.py` - メイン実装
- `tests/task_count/__init__.py` - テストパッケージ
- `tests/task_count/test_list_by_phase.py` - テストコード
- `docs/command_reference/task_count/index.rst` - ドキュメント（インデックス）
- `docs/command_reference/task_count/list_by_phase.rst` - ドキュメント（詳細）

### 変更ファイル

- `annofabcli/__main__.py` - task_countコマンドの登録
- `docs/command_reference/index.rst` - task_countドキュメントへのリンク追加

## コマンド仕様

### コマンド名の選択理由

#### `task_count` vs `task_summary`

**採用: `task_count`**

- 理由: より具体的で明確
  - `task_count` は「タスクの数」を出力することが明確
  - `task_summary` は抽象的で、何を集計するのか分かりにくい
  - 他のコマンド（`statistics`, `stat_visualization`など）との命名の一貫性

#### `list_by_phase` vs `phase_status`

**採用: `list_by_phase`**

- 理由: アクションが明確で一貫性がある
  - `list` は他のコマンド（`task list`, `input_data list`など）と統一された動詞
  - `by_phase` でフェーズごとの集計であることが明確
  - `phase_status` は名詞的で、コマンドの動作（リスト出力）が分かりにくい

### タスク状態の分類

タスクを以下の6つのカテゴリに分類して集計します：

1. **`never_worked.unassigned`** - 一度も作業していない状態かつ担当者未割り当て
2. **`never_worked.assigned`** - 一度も作業していない状態かつ担当者割り当て済み
3. **`worked.not_rejected`** - 作業中または休憩中で、まだ差し戻されていない
4. **`worked.rejected`** - 作業中または休憩中で、次のフェーズで差し戻された
5. **`on_hold`** - 保留中
6. **`complete`** - 完了

#### 分類の設計理由

- Annofabの`TaskStatus`（NOT_STARTED, WORKING, BREAK, ON_HOLD, COMPLETE）をそのまま使うのではなく、ユーザーが知りたい粒度で分類
- 未着手タスクを「担当者あり/なし」で分けることで、アサイン状況を把握可能
- 作業中タスクを「差し戻しあり/なし」で分けることで、品質状況を把握可能
- タスクの進捗と問題点を一目で把握できるようにする

### 主要な機能

#### 1. 作業時間閾値の指定 (`--not_worked_threshold_second`)

```bash
annofabcli task_count list_by_phase --project_id prj1 --not_worked_threshold_second 60
```

- **目的**: 数秒だけ開いて閉じたタスクを「未着手」として扱う
- **デフォルト**: 0秒（少しでも作業していれば「作業済み」とみなす）
- **用途例**: 60秒以下の作業を誤操作とみなす場合など

#### 2. メタデータキーでのグループ化 (`--metadata_key`)

```bash
annofabcli task_count list_by_phase --project_id prj1 --metadata_key dataset_type category
```

- **目的**: タスクのメタデータの値ごとにタスク数を集計
- **複数指定可**: 複数のメタデータキーを指定可能
- **用途例**: データセットタイプ別、カテゴリ別の進捗把握

#### 3. ダウンロード方式の選択

**デフォルト**: タスク全件ファイルをダウンロード（推奨）

```bash
annofabcli task_count list_by_phase --project_id prj1
```

**オプション**: `getTasks` APIを実行

```bash
annofabcli task_count list_by_phase --project_id prj1 --execute_get_tasks_api
```

- タスク全件ファイルのダウンロードが推奨（高速）
- APIを直接実行する方式は、リアルタイム性が必要な場合のみ

## 技術的な実装の選択

### 1. `DownloadingFile`クラスの使用

- **理由**: 
  - 既存の`download.py`の実装を再利用
  - タスク全件ファイル、タスク履歴全件ファイルのダウンロード処理を統一
  - 一時ディレクトリの管理を適切に行う

### 2. タスク履歴の参照

- **目的**: 各フェーズでの作業時間を正確に取得
- **実装**: `task_history`から各フェーズの`accumulated_labor_time_milliseconds`を集計
- **理由**: タスク情報だけでは現在のフェーズの作業時間しか分からないため

### 3. pandas DataFrameの使用

- **目的**: 集計処理の簡潔な実装
- **機能**: 
  - `pivot_table`でフェーズ×タスク状態のクロス集計
  - メタデータキーを動的に列として追加
  - ソート処理（annotation → inspection → acceptance）

## 出力例

### 基本的な出力

```csv
phase,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete
annotation,10,5,8,2,1,74
inspection,0,0,12,3,0,85
acceptance,0,0,8,0,0,92
```

### メタデータキーを指定した出力

```csv
phase,metadata.dataset_type,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete
annotation,train,8,3,5,1,1,42
annotation,validation,2,2,3,1,0,32
inspection,train,0,0,8,2,0,48
inspection,validation,0,0,4,1,0,37
acceptance,train,0,0,5,0,0,53
acceptance,validation,0,0,3,0,0,39
```

## 今後の拡張可能性

- フェーズステージ（多段検査）ごとの集計
- 担当者ごとの集計
- 日付範囲の指定
- タスク状態の遷移履歴の可視化

## 関連Issue/Discussion

（該当する場合は記入）

## テスト

- `tests/task_count/test_list_by_phase.py`にテストコードを追加
  - 基本的な使い方
  - 閾値指定のテスト
  - メタデータキー指定のテスト

## ドキュメント

- `docs/command_reference/task_count/list_by_phase.rst`にドキュメントを追加
  - コマンドの説明
  - 使用例
  - 出力例
  - argparseからの自動生成ドキュメント
