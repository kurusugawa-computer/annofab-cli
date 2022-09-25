# annofab-cli
[Annofab](https://annofab.com/)のCLI(Command Line Interface)ツールです。
「タスクの一括差し戻し」や、「タスク一覧出力」など、Annofabの画面で実施するには時間がかかる操作を、コマンドとして提供しています。

[![Build Status](https://app.travis-ci.com/kurusugawa-computer/annofab-cli.svg?branch=main)](https://app.travis-ci.com/kurusugawa-computer/annofab-cli)
[![PyPI version](https://badge.fury.io/py/annofabcli.svg)](https://badge.fury.io/py/annofabcli)
[![Python Versions](https://img.shields.io/pypi/pyversions/annofabcli.svg)](https://pypi.org/project/annofabcli/)
[![Documentation Status](https://readthedocs.org/projects/annofab-cli/badge/?version=latest)](https://annofab-cli.readthedocs.io/ja/latest/?badge=latest)


* **Annofab:** https://annofab.com/
* **Documentation:** https://annofab-cli.readthedocs.io/ja/latest/




# 注意
* 作者または著作権者は、ソフトウェアに関してなんら責任を負いません。
* 予告なく互換性のない変更がある可能性をご了承ください。
* Annofabプロジェクトに大きな変更を及ぼすコマンドも存在します。間違えて実行してしまわないよう、注意してご利用ください。


## 廃止予定


### 2022-09-01 以降
* `input_data put`コマンドでZIPファイルの登録する機能を廃止します。替わりに`input_data put_with_`コマンドはご利用ください。

### 2022-11-01 以降
* JMESPathを指定できる `--query`を削除します。使いどころがあまりないのと、`jq`コマンドでも対応できるためです。
* `--wait_options`を削除します。使いどころがあまりないためです。

### 2022-12-01 以降
* `filesystem write_annotation_image`を2022-12-01以降に廃止する予定です。替わりに`filesystem draw_annotation`コマンドを利用してください。
* `inspection_comment` コマンド配下を2022-12-01以降に廃止する予定です。替わりに`comment`コマンドを利用してください。

# Requirements
* Python 3.8+

# Install

```
$ pip install annofabcli
```

https://pypi.org/project/annofabcli/

## Windows用の実行ファイルを利用する場合
[GitHubのリリースページ](https://github.com/kurusugawa-computer/annofab-cli/releases)から`annofabcli-vX.X.X-windows.zip`をダウンロードしてください。
zipの中にある`annofabcli.exe`が実行ファイルになります。


## Dockerを利用する場合

```
$ git clone https://github.com/kurusugawa-computer/annofab-cli.git
$ cd annofab-cli
$ chmod u+x docker-build.sh
$ ./docker-build.sh

$ docker run -it annofab-cli --help

# Annofabの認証情報を標準入力から指定する
$ docker run -it annofab-cli project diff prj1 prj2
Enter Annofab User ID: XXXXXX
Enter Annofab Password: 

# Annofabの認証情報を環境変数で指定する
$ docker run -it -e ANNOFAB_USER_ID=XXXX -e ANNOFAB_PASSWORD=YYYYY annofab-cli project diff prj1 prj2
```


## Annofabの認証情報の設定
https://annofab-cli.readthedocs.io/ja/latest/user_guide/configurations.html 参照

# 使い方
https://annofab-cli.readthedocs.io/ja/latest/user_guide/index.html 参照

# コマンド一覧
https://annofab-cli.readthedocs.io/ja/latest/command_reference/index.html


# よくある使い方

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

# 補足

# Windowsでannofabcliを使う場合
WindowsのコマンドプロンプトやPowerShellでannofabcliを使う場合、JSON文字列内の二重引用をエスケープする必要があります。

```
> annofabcli task list --project_id prj1  --task_query '{"\status\": \"complete\"}'
```
