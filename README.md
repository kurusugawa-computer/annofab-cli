[![Build Status](https://travis-ci.com/kurusugawa-computer/annofab-cli.svg?branch=master)](https://travis-ci.com/kurusugawa-computer/annofab-api-python-client)
[![PyPI version](https://badge.fury.io/py/annofabcli.svg)](https://badge.fury.io/py/annofabcli)
[![Python Versions](https://img.shields.io/pypi/pyversions/annofabcli.svg)](https://pypi.org/project/annofabcli/)



# 概要
AnnoFabのCLI(Command Line Interface)ツールです。
「タスクの一括差し戻し」や、「プロジェクト間の差分表示」など、AnnoFabの画面で実施するには時間がかかる操作を、コマンドとして提供しています。

# 注意
* 作者または著作権者は、ソフトウェアに関してなんら責任を負いません。
* 予告なく互換性のない変更がある可能性をご了承ください。
* AnnoFabプロジェクトに大きな変更を及ぼすコマンドも存在します。間違えて実行してしまわないよう、注意してご利用ください。


## 廃止予定
* 2020-04-01以降：`annofabcli filesystem write_annotation_image`コマンドの`--metadata_key_of_image_size`を廃止します。入力データから画像サイズを取得できるようになったためです。
* 2020-04-01以降：`annofabcli inspection_comment list_unprocessed`コマンドを廃止します。`inspection_comment list`コマンドを組み合わせて同様のことが実現できるからです。



# Requirements
* Python 3.7.1+

# Install

```
$ pip install annofabcli
```

https://pypi.org/project/annofabcli/


## AnnoFabの認証情報の設定
AnnoFabの認証情報を設定する方法は2つあります。
* `.netrc`ファイル
* 環境変数`ANNOFAB_USER_ID` , `ANNOFAB_PASSWORD`

`.netrc`ファイルへの記載方法は、[annofab-api-python-client/README.md](https://github.com/kurusugawa-computer/annofab-api-python-client#netrc%E3%81%AB%E8%A8%98%E8%BC%89%E3%81%95%E3%82%8C%E3%81%9Fuser_id-password%E3%81%8B%E3%82%89%E7%94%9F%E6%88%90)を参照してください。

AnnoFabの認証情報が設定されていない状態で`annofabcli`コマンドを実行すると、標準入力からAnnoFabの認証情報を入力できるようになります。

```
$ annofabcli project diff aaa bbb
Enter AnnoFab User ID: XXXXXX
Enter AnnoFab Password: 
```

AnnoFabの認証情報の優先順位は以下の通りです。
1. `.netrc`ファイル
2. 環境変数

## AnnoFab WebAPIのエンドポイントの設定（開発者用）
AnnoFab WebAPIのエンドポイントを指定できます。デフォルトは https://annofab.com です。
* コマンドライン引数`--endpoint_url`
* 環境変数 `ANNOFAB_ENDPOINT_URL`

設定したエンドポイントURLの優先順位は以下の通りです。
1. コマンドライン引数
2. 環境変数


## Dockerを利用する場合

```
$ git clone https://github.com/kurusugawa-computer/annofab-cli.git
$ cd annofab-cli
$ chmod u+x docker-build.sh
$ ./docker-build.sh

$ docker run -it annofab-cli --help

# AnnoFabの認証情報を標準入力から指定する
$ docker run -it annofab-cli project diff prj1 prj2
Enter AnnoFab User ID: XXXXXX
Enter AnnoFab Password: 

# AnnoFabの認証情報を環境変数で指定する
$ docker run -it -e ANNOFAB_USER_ID=XXXX -e ANNOFAB_PASSWORD=YYYYY annofab-cli project diff prj1 prj2
```

# コマンド一覧
https://annofab-cli.readthedocs.io/ja/latest/command_reference/index.html

# Usage


## すべてのコマンドで共通のオプション引数

### `--disable_log`
ログを無効化にします。


### `--endpoint_url`
AnnoFab WebAPIのエンドポイントURLを指定します。デフォルトは https://annofab.com です。


### `-h` / `--help`
コマンドのヘルプを出力します。

```
# annofabcli全体のヘルプ
$ annofabcli -h

# project diff コマンドのヘルプ
$ annofabcli project diff -h
```


### `--logdir`
ログファイルを保存するディレクトリを指定します。指定しない場合、`.log`ディレクトリにログファイルを出力します。


### `--logging_yaml`
以下のような、ロギグングの設定ファイル(YAML)を指定します。指定した場合、`--logdir`オプションは無視されます。指定しない場合、デフォルトのロギング設定ファイルが読み込まれます。
設定ファイルの書き方は https://docs.python.org/ja/3/howto/logging.html を参照してください。

```yaml:logging-sample.yaml
# WARNINGレベル以上のログをコンソールに出力する

version: 1
handlers:
  consoleHandler:
    class: logging.StreamHandler
root:
  level: WARNING
  handlers: [consoleHandler]

# デフォルトのロガーを無効化しないようにする https://docs.djangoproject.com/ja/2.1/topics/logging/#configuring-logging
disable_existing_loggers: False
```


### `--yes`
処理中に現れる問い合わせに対して、常に'yes'と回答します。


## ほとんどのコマンドで共通のオプション引数


### `--csv_format`
CSVのフォーマットをJSON形式で指定します。`--format`が`csv`でないときは、このオプションは無視されます。
先頭に`file://`を付けると、JSON形式のファイルを指定できます。
指定した値は、[pandas.DataFrame.to_csv](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_csv.html) の引数として渡されます。
デフォルトはカンマ区切り、BOM付きUTF-8エンコーディングです。

```
--csv_format '{"sep": "\t"}'
```


### `-f` / `--format`
list系のコマンドで、出力フォーマットを指定します。多くのコマンドでは、以下のフォーマットが指定できます。
* `csv` : CSV(デフォルとはカンマ区切り)
* `json` : インデントや空白がないJSON
* `pretty_json` : インデントされたJSON





### `-o` / `--output`
出力先のファイルパスを指定します。指定しない場合は、標準出力に出力されます。
主にlist系のコマンドで利用できます。

### `--parallelism`
並列数を指定します。指定しない場合は、逐次的に処理します。


### `-p` / `--project_id`
対象のプロジェクトのproject_idを指定します。

### `-q` / `--query`
[JMESPath](http://jmespath.org/) を指定します。出力結果の抽出や、出力内容の変更に利用できます。


### `-t` / `--task_id`
対象のタスクのtask_idを指定します。`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。

* 相対パスで指定： `--task_id file://task.txt`
* 絶対パスで指定： `--task_id file:///tmp/task.txt`


## デフォルトのログ設定
* ログは、標準エラー出力とログファイルに出力されます。
* カレントディレクトリの`.log`ディレクトリに、`annofabcli.log`というログファイルが生成されます。
* `annofabcli.log`ファイルは、1日ごとにログロテート（新しいログファイルが生成）されます

デフォルトログは https://github.com/kurusugawa-computer/annofab-cli/blob/master/annofabcli/data/logging.yaml で定義されています。


## よくある使い方

### 受入完了状態のタスクを差し戻す
"car"ラベルの"occluded"属性のアノテーションルールに間違いがあったため、以下の条件を満たすタスクを一括で差し戻します。
* "car"ラベルの"occluded"チェックボックスがONのアノテーションが、タスクに1つ以上存在する。

前提条件
* プロジェクトのオーナが、annofabcliコマンドを実行する


```
# 受入完了のタスクのtask_id一覧を、acceptance_complete_task_id.txtに出力する。
$ annofabcli task list --project_id prj1  --task_query '{"status": "complete","phase":"acceptance"}' \
 --format task_id_list --output acceptance_complete_task_id.txt

# 受入完了タスクの中で、 "car"ラベルの"occluded"チェックボックスがONのアノテーションの個数を出力する。
$ annofabcli annotation list_count --project_id prj1 --task_id file://task.txt --output annotation_count.csv \
 --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}'

# annotation_count.csvを表計算ソフトで開き、アノテーションの個数が1個以上のタスクのtask_id一覧を、task_id.txtに保存する。

# task_id.txtに記載されたタスクを差し戻す。検査コメントは「carラベルのoccluded属性を見直してください」。
# 差し戻したタスクには、最後のannotation phaseを担当したユーザを割り当てる（画面と同じ動き）。
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt --cancel_acceptance \
  --comment "carラベルのoccluded属性を見直してください"

```

### プロジェクトメンバをCSVで管理する

```
# prj1のプロジェクトメンバをCSVで出力する
$ annofabcli project_member list --project_id prj1 --format csv --output members.csv \
 --csv_format '{"columns": ["user_id","member_role","sampling_inspection_rate","sampling_acceptance_rate"],"header":false}' 


# members.csvの中身を確認
$ head members.csv
user1,worker
user2,accepter
...


# members.csvに記載れたメンバを prj2に登録する
$ annofabcli project_member put --project_id prj2 --csv members.csv

```


## コマンド一覧

### annotation
https://annofab-cli.readthedocs.io/ja/latest/command_reference/annotation/index.html 参照


### annotation_specs
https://annofab-cli.readthedocs.io/ja/latest/command_reference/annotation_specs/index.html 参照

### filesystem
https://annofab-cli.readthedocs.io/ja/latest/command_reference/filesystem/index.html 参照

### input_data 
https://annofab-cli.readthedocs.io/ja/latest/command_reference/input_data/index.html 参照

### inspection_comment
https://annofab-cli.readthedocs.io/ja/latest/command_reference/inspection_comment/index.html 参照

### instruction
https://annofab-cli.readthedocs.io/ja/latest/command_reference/instruction/index.html 参照


### job
https://annofab-cli.readthedocs.io/ja/latest/command_reference/job/index.html 参照






### project
https://annofab-cli.readthedocs.io/ja/latest/command_reference/project/index.html 参照

### project_member
https://annofab-cli.readthedocs.io/ja/latest/command_reference/project_member/index.html 参照






### supplementary
https://annofab-cli.readthedocs.io/ja/latest/command_reference/supplementary/index.html 参照


### task
https://annofab-cli.readthedocs.io/ja/latest/command_reference/task/index.html 参照

### task_history
https://annofab-cli.readthedocs.io/ja/latest/command_reference/task_history/index.html 参照
