# ADR-0001: list_3d_bounding_box_annotationコマンドに属性情報出力を追加

## ステータス

承認済み

## 日付

2026-01-07

## コンテキスト

`annotation_zip list_3d_bounding_box_annotation`コマンドは、アノテーションZIPから3Dバウンディングボックス（CUBOID）アノテーションの座標情報を出力するコマンドです。

ユーザーから以下の要望がありました：
- 区間の長さ情報と属性値を比較しながら確認したい
- 3Dバウンディングボックスの座標情報だけでなく、属性情報（例: occluded, type）も一緒に出力したい

現状では座標情報（dimensions, location, rotation等）のみが出力され、属性情報は出力されていませんでした。

## 決定

`annotation_zip list_3d_bounding_box_annotation`コマンドに属性情報の出力機能を追加しました。

### 実装内容

1. **データモデルの拡張**
   - `Annotation3DBoundingBoxInfo`データクラスに`attributes: dict[str, str | int | bool]`フィールドを追加
   - `updated_datetime`（Optional型）の後に配置し、dataclassのフィールド順序の制約に対応

2. **出力形式**
   - **JSON形式**: `attributes`オブジェクトとして出力
     ```json
     {
       "annotation_id": "...",
       "attributes": {
         "occluded": true,
         "type": "sedan"
       }
     }
     ```
   - **CSV形式**: `attributes.属性名`の形式で列を追加（例: `attributes.occluded`, `attributes.type`）
   - `pandas.json_normalize`を使用してネストされた構造を展開

3. **エッジケース対応**
   - 空のリストの場合でも、`base_columns`のヘッダ行が出力されるように対応
   - `len(tmp_annotation_bbox_list) == 0`の場合、`pandas.DataFrame(columns=base_columns)`を返す

4. **テストカバレッジ**
   - 属性値が設定されている場合のテスト
   - CSV形式での属性列出力の確認
   - JSON形式での属性オブジェクト出力の確認
   - 空のリストの場合のテスト

### 参考実装

`statistics list_annotation_attribute`コマンドと同じ出力形式を採用し、ユーザーが一貫した形式で属性情報を扱えるようにしました。

## 代替案

### 代替案1: 属性情報を別のコマンドで出力

**概要**: 属性情報を出力する専用のコマンドを作成し、`list_3d_bounding_box_annotation`は座標情報のみに特化させる。

**却下理由**:
- ユーザーが2つのコマンドを実行して結果をマージする必要があり、使い勝手が悪い
- データの不整合が発生する可能性がある
- `statistics list_annotation_attribute`は既に存在するが、3Dバウンディングボックス特有の座標情報は含まれない

### 代替案2: オプション引数で属性情報出力を制御

**概要**: `--include-attributes`のようなオプションを追加し、デフォルトでは属性情報を出力しない。

**却下理由**:
- 既存のユーザーへの影響がほぼない（属性列が追加されるだけ）
- オプションの追加により複雑性が増す
- CSV形式では列が動的に追加されるため、デフォルトで含める方が自然

### 代替案3: direction情報も常にCSV出力に含める

**概要**: `direction.front.x`, `direction.up.z`などの列も追加する。

**却下理由**:
- `direction`は既に`rotation`から算出可能
- CSV列数が大幅に増加し、可読性が低下
- 現在の実装では、必要に応じてJSON形式で確認できる

## 結果

### ポジティブ

- ユーザーは1つのコマンドで座標情報と属性情報の両方を取得できる
- `statistics list_annotation_attribute`と一貫した出力形式
- CSV/JSON両形式で属性情報が利用可能
- 空のリストの場合でもヘッダ行が出力されるため、後続処理が安定

### ネガティブ

- CSV出力時、属性が多い場合に列数が増加する可能性
  - 対策: `pandas.json_normalize`により、実際に存在する属性のみが列として追加される
- 既存のCSV出力に列が追加されるため、列位置に依存する処理に影響する可能性
  - 影響範囲: 軽微（属性列は既存列の後に追加されるため）

### ネガティブへの対策

特に対策は不要と判断しました。理由：
- CSV列数の増加は、実際に存在する属性のみに限定される
- 列位置への依存は、列名でアクセスすることで回避可能（推奨される方法）

## 関連する決定

- [statistics list_annotation_attribute コマンドの実装](https://annofab-cli.readthedocs.io/ja/latest/command_reference/statistics/list_annotation_attribute.html)

## 参考資料

- GitHub Issue: （該当する場合は記載）
- ユーザーからの要望: 「区間の長さ情報と属性値を比較しながら確認したい」
- 実装PR: （該当する場合は記載）
