# copilot-instructions.md

## プロジェクトの目的
AnnofabのCLIです。

## 開発でよく使うコマンド
* コードのフォーマット: `make format`
* Lintの実行: `make lint`
* テストの実行: `make test`
* ドキュメントの実行: `make docs`

## 技術スタック
* Python 3.9 以上
* テストフレームワーク: Pytest v8 以上

## ディレクトリ構造概要

* `annofabcli/**`: アプリケーションのソースコード
* `tests/**`: テストコード
* `tests/data/**`: テストコードが参照するリソース


## コーディングスタイル

### Python
* できるだけ型ヒントを付ける
* docstringはGoogleスタイル

## レビュー
* PRレビューの際は、日本語でレビューを行う