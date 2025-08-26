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
* `docs/*`: ドキュメント
    * `docs/command_reference/**`: コマンドリファレンス

## コーディングスタイル

### Python
* dictから値を取得する際、必須なキーならばブラケット記法を使う。キーが必須がどうか分からない場合は、必須とみなす。
* できるだけ`os.path`でなく`pathlib.Path`を使う（Lint`flake8-use-pathlib`に従う）
* Noneの判定、空文字列の判定、長さが0のコレクションの判定は、falsyとして判定するのでなく、`if a is not None:`のように判定内容を明記してください。

### テストコード
* Errorの確認は、`pytest.raises`を使用する。エラーメッセージの確認は行わない。
* テストファイルは、`test_*.py`の形式で作成する。ディレクトリ構成は`src`と対応させる。
* 一時ディレクトリを使用する場合は、`tmp_path` fixtureを利用する。

### ドキュメント
* コマンドのドキュメントは、`docs/command_reference/`に作成する。
* コマンドの末尾には以下のように`.. argparse::`ディレクティブを追加して、`argparse`から自動生成されるUsage Detailsセクションを挿入する。

```
Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.list_comment.add_parser
    :prog: annofabcli comment list
    :nosubcommands:
    :nodefaultconst:
```

## レビュー
* PRレビューの際は、日本語でレビューを行う
