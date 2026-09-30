---
name: annofab-cli
description: annofab-cliを使ってAnnofabから情報を取得したり、操作したりするときに使用します。annofab-cli自体の開発には使用しません。
---

# annofab-cli
ユーザーから依頼されたAnnofabの操作には、`annofabcli`を使用してください。

## コマンドの調べ方
- 使用するコマンドが明確でない場合は、[コマンド索引](references/command-index.md)を参照してください。
- コマンドを実行する前に`annofabcli <command> <subcommand> --help`を実行して、ヘルプを確認してください。コマンド名やオプションを推測しないでください。
- `--help`オプションのヘルプだけでは情報が不足している場合は、[ドキュメントのコマンドリファレンス](https://annofab-cli.readthedocs.io/ja/latest/command_reference/index.html)を参照してください。
- バージョンによって動作が異なる可能性がある場合は、`annofabcli --version`でインストール済みのバージョンを確認してください。

### 参考サイト
* [GitHubリポジトリ](https://github.com/kurusugawa-computer/annofab-cli)
* [Annofabのマニュアル](https://annofab.readme.io/docs/)

## リソースを変更するコマンド
* ユーザーからの指示がない限り、タスクやアノテーションなどのリソースを変更するコマンドを実行しないでください。
* ユーザーからの指示がない限り、`--yes`オプションを付けてコマンドを提示または実行しないでください。間違えて実行した際の影響が大きいためです。
* リソースを変更した後は、可能であれば適切な読み取り専用コマンドで結果を確認してください。
    
