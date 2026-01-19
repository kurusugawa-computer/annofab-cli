# Pull Request: task_count list_by_phaseコマンドの実装

## 概要

フェーズごとのタスク数をCSV形式で出力する `task_count list_by_phase` コマンドを新規作成しました。

プロジェクトの現在のタスクの状態（未着手/作業中/完了など）をフェーズごとに一目で把握できるコマンドです。

## 変更内容

### 新規作成

- `annofabcli/task_count/` - 新規パッケージ
  - `list_by_phase.py` - メイン実装
  - `subcommand_task_count.py` - サブコマンド登録
- `tests/task_count/test_list_by_phase.py` - テストコード
- `docs/command_reference/task_count/` - ドキュメント

### 主な機能

1. **タスク状態の6分類**
   - `never_worked.unassigned` - 未着手・未割り当て
   - `never_worked.assigned` - 未着手・割り当て済み
   - `worked.not_rejected` - 作業中・差し戻しなし
   - `worked.rejected` - 作業中・差し戻しあり
   - `on_hold` - 保留中
   - `complete` - 完了

2. **作業時間閾値の指定** (`--not_worked_threshold_second`)
   - 指定秒数以下の作業を「未着手」とみなす機能

3. **メタデータキーでのグループ化** (`--metadata_key`)
   - データセットタイプ別、カテゴリ別などで集計可能

## 使用例

```bash
# 基本的な使い方
annofabcli task_count list_by_phase --project_id prj1 --output out.csv

# 60秒以下を未着手とみなす
annofabcli task_count list_by_phase --project_id prj1 --not_worked_threshold_second 60

# メタデータでグループ化
annofabcli task_count list_by_phase --project_id prj1 --metadata_key dataset_type category
```

## 出力例

```csv
phase,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete
annotation,10,5,8,2,1,74
inspection,0,0,12,3,0,85
acceptance,0,0,8,0,0,92
```

## 設計上の検討事項

詳細は [docs/prompts/20260119-task-count-list-by-phase.md](docs/prompts/20260119-task-count-list-by-phase.md) を参照してください。

### コマンド名

- `task_count` を採用（理由: 具体的で明確）
- `list_by_phase` を採用（理由: 他コマンドとの一貫性）

### 技術選択

- `DownloadingFile`クラスを使用（タスク全件ファイルのダウンロード）
- pandas DataFrameで集計処理（pivot_tableの活用）
- タスク履歴を参照して作業時間を正確に取得

## テスト

- [x] `make lint` 成功
- [x] `make format` 実行済み
- [x] テストコード作成済み
- [x] ドキュメント作成済み

## チェックリスト

- [x] コードの実装
- [x] テストコードの作成
- [x] ドキュメントの作成
- [x] Lint/フォーマットチェック通過
- [x] 設計の検討内容を文書化

## 関連コミット

```
AIが生成: task_count list_by_phaseコマンドの実装詳細をドキュメント化
AIが生成: task_count list_by_phaseコマンドのテストコードとドキュメントを追加
AIが生成: メタデータキーでの集計機能を追加
AIが生成: 作業時間の閾値を指定できるように変更、DownloadingFileクラスを使用
AIが生成: task_count list_by_phaseコマンドを追加
AIが生成: task_countサブコマンドの作成
```
