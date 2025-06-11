# 概要
* annofabcliとは、CLIでAnnofabを操作するコマンドです。


# ユーザーインターフェイス
* できるだけ、他のコマンドと引数の名前や使い方を揃えてください。詳細は https://annofab-cli.readthedocs.io/ja/latest/user_guide/command_line_options.html を参照してください。
* 副作用があるコマンドは、標準出力でyes/noを問い合わせてください。

# 開発

## スタイルと言語
* Python 3.9以上で動くコードにしてください。
* できるだけ型ヒントを付けてください。
* Annofab Web API へのアクセスは、[annofabapi](https://github.com/kurusugawa-computer/annofab-api-python-client)を使ってください。
* ユーザーにyes/noを問い合わせる場合は、`annofabcli.common.cli.CommandLineWithConfirm`を継承して、`confirm_processing`メソッドを使ってください。
* `typing.Dict`や`typing.List`など、Python3.9で非推奨になったクラスは使わないでください。
* 原則、`import`文はファイルの先頭に記述してください。関数の内部でimportしないでください。
* 新しくコマンドを作成したら、`docs/command_reference`配下にreStructuredTextでドキュメントを記載してください。

