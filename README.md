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
* 2020-10-01以降：Pythonのサポートバージョンを3.6以上から、3.7以上に変更します。
* 2020-09-01以降：`input_data list`コマンドの`--batch`オプションを削除します。入力データを１万件以上取得したい場合は、`project download input_data`コマンドを利用してください。

# Requirements
* Python 3.6+

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

$ docker run -it annofab-cli annofabcli --help

# AnnoFabの認証情報を標準入力から指定する
$ docker run -it annofab-cli annofabcli project diff prj1 prj2
Enter AnnoFab User ID: XXXXXX
Enter AnnoFab Password: 

# AnnoFabの認証情報を環境変数で指定する
$ docker run -it -e ANNOFAB_USER_ID=XXXX -e ANNOFAB_PASSWORD=YYYYY annofab-cli annofabcli project diff prj1 prj2
```

# 機能一覧

|コマンド| サブコマンド                  | 内容                                                                                                     |必要なロール|
|----|-------------------------------|----------------------------------------------------------------------------------------------------------|------------|
|annotation| change_attributes |アノテーションの属性を変更します。                              |オーナ|
|annotation| delete | アノテーションを削除します。                              |オーナ|
|annotation| dump | アノテーション情報をファイルに保存します。                             |-|
|annotation| list_count | task_idまたはinput_data_idで集約したアノテーションの個数を出力します                              |-|
|annotation| import | アノテーションをインポートします。                             |オーナ|
|annotation| restore |'annotation dump'コマンドで保存したファイルから、アノテーション情報をリストアします。                            |オーナ|
|annotation_specs| history | アノテーション仕様の履歴一覧を出力します。                              |-|
|annotation_specs| list_label | アノテーション仕様のラベル情報を出力します。                              |-|
|annotation_specs| list_label_color             | アノテーション仕様から、label_nameとRGBを対応付けたJSONを出力します。                                      |-|
|filesystem| write_annotation_image        | アノテーションzip、またはそれを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成します。 |-|
|input_data|delete             | 入力データを削除します。                                                            |オーナ|
|input_data|list             | 入力データ一覧を出力します。                                                            |-|
|input_data| list_merged_task | タスク一覧と結合した入力データ一覧のCSVを出力します。                                                            |オーナ/アノテーションユーザ|
|input_data|put             | 入力データを登録します。                                                            |オーナ|
|input_data|update_metadata             | 入力データのメタデータを更新します。                                                            |オーナ|
|inspection_comment| list | 検査コメントを出力します。                               |-|
|inspection_comment| list_unprocessed | 未処置の検査コメントを出力します。                               |-|
|instruction| copy             | 作業ガイドをコピーします。                                                         |チェッカー/オーナ|
|instruction| upload             | HTMLファイルを作業ガイドとして登録します。                                                           |チェッカー/オーナ|
|job|delete             | ジョブを削除します。                                                            |オーナ|
|job|list             | ジョブ一覧を出力します。                                                            |-|
|job|list_last             | 複数のプロジェクトに対して、最新のジョブを出力します。                                                            |-|
|labor|list_worktime_by_user | ユーザごとに作業予定時間、作業実績時間を出力します。                                                          ||
|organization_member|list             | 組織メンバ一覧を出力します。                                                            |-|
|project| copy                 | プロジェクトをコピーします。                                                                           |オーナ and 組織管理者/組織オーナ|
|project| diff                 | プロジェクト間の差分を表示します。                                                                           |チェッカー/オーナ|
|project| download                 | タスクや検査コメント、アノテーションなどをダウンロードします。                                                                           |オーナ|
|project| list                 | プロジェクト一覧を出力します。                                                                          |-|
|project| update_annotation_zip                 | アノテーションzipを更新します。                                                                         |オーナ/アノテーションユーザ|
|project_member| change                  | プロジェクトメンバを変更します。|オーナ|
|project_member| copy                  | プロジェクトメンバをコピーします。|オーナ(コピー先プロジェクトに対して)|
|project_member| delete                  | 複数のプロジェクトからユーザを削除します。                                                                 |オーナ|
|project_member| invite                  | 複数のプロジェクトに、ユーザを招待します。                                                                 |オーナ|
|project_member| list                  | プロジェクトメンバ一覧を出力します。                                                                |-|
|project_member| put                  | CSVに記載されたユーザを、プロジェクトメンバとして登録します。|オーナ|
|statistics| list_annotation_count             | 各ラベル、各属性値のアノテーション数を、タスクごと/入力データごとに出力します。                                                   |-|
|statistics| list_by_date_user             | タスク数や作業時間などの情報を、日ごとユーザごとに出力します。                                                   |オーナ/アノテーションユーザ|
|statistics| list_cumulative_labor_time             |       タスク進捗状況を出力します。                                                    |-|
|statistics| list_task_progress             | タスクフェーズ別の累積作業時間を出力します。                                                            |-|
|statistics|summarize_task_count|タスクのフェーズ、ステータス、ステップごとにタスク数を出力します。|オーナ/アノテーションユーザ|
|statistics|summarize_task_count_by_task_id|task_idのプレフィックスごとに、タスク数を出力します。|オーナ/アノテーションユーザ|
|statistics|summarize_task_count_by_user|ユーザごとに担当しているタスク数を出力します。|オーナ/アノテーションユーザ|
|statistics| visualize             | 統計情報を可視化します。                                                            |オーナ/アノテーションユーザ|
|supplementary| list             | 補助情報を出力します。                                                           |オーナ/アノテーションユーザ|
|supplementary| put              | 補助情報を登録します。                                                           |オーナ|
|task| cancel_acceptance             | 受け入れ完了タスクを、受け入れ取り消し状態にします。                                                         |オーナ|
|task| change_operator             | タスクの担当者を変更します。                                                             |チェッカー/オーナ|
|task| complete                | タスクを完了状態にして次のフェーズに進めます（教師付の提出、検査/受入の合格）。                                  |チェッカー/オーナ|
|task| delete                | タスクを削除します。                                 |オーナ|
|task|list             | タスク一覧を出力します。                                                            |-|
|task|list_added_task_history             | タスク履歴情報を加えたタスク一覧を出力します。|オーナ/アノテーションユーザ|
|task|list_task_history             | タスク履歴の一覧を出力します。|-|
|task| put                | タスクを作成します。                                 |オーナ|
|task| reject                  | タスクを強制的に差し戻します。                                                                 |オーナ|


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

### annotation change_attributes
アノテーションの属性を一括で変更します。ただし、作業中状態のタスクのアノテーションの属性は変更できません。間違えてアノテーション属性を変更したときに復元できるようにするため、`--backup`でバックアップ用のディレクトリを指定することを推奨します。

```
# task.txtに記載されたタスクのアノテーションの属性をを変更する
# carラベルのoccludedチェックボックスがTRUEのアノテーションに対して、occludedチェックボックスをOFFにする
$ annofabcli annotation change_attributes --project_id prj1 --task_id file://task.txt \ 
--annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}' \
--attributes '[{"additional_data_definition_name_en": "occluded", "flag": false}]' \
--backup backup_dir


```




### annotation delete
タスク配下のアノテーションを削除します。ただし、作業中/完了状態のタスク、または「過去に割り当てられていて現在の担当者が自分自身でない」タスクのアノテーションは削除できません。

間違えてアノテーションを削除してしまっときに復元できるようにするため、`--backup`でバックアップ用のディレクトリを指定することを推奨します。バックアップ用ディレクトリには、 [annotation dump](#annotation-dump) コマンドの出力結果と同等のアノテーション情報が保存されます。
アノテーションの復元には [annotation restore](#annotation-restore) コマンドを使用してください。


```
# task.txtに記載されたタスクのアノテーションを削除します。削除する前のアノテーション情報は、`backup`ディレクトリに保存します。
$ annofabcli annotation delete --project_id prj1 --task_id file://task.txt --backup backup

# carラベルのoccludedチェックボックスがTRUEのアノテーションを削除します
$ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \ 
--annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}' \
--backup backup_dir
```

### annotation dump
指定したタスク配下のアノテーション情報をディレクトリに保存します。アノテーションをバックアップしたいときなどに利用できます。
アノテーションの復元には [annotation restore](#annotation-restore) コマンドを使用してください。


```
# task.txtに記載されたタスクのアノテーションを、`output`ディレクトリに保存します。
$ annofabcli annotation dump --project_id prj1 --task_id file://task.txt --output backup-dir
```

バックアップディレクトリは、以下のディレクトリ構成です（Simpleアノテーション(v2)と同じディレクトリ構成）。
`{input_data_id}.json`のフォーマットは、[getEditorAnnotation](https://annofab.com/docs/api/#operation/getEditorAnnotation) APIのレスポンスと同じです。

```
ルートディレクトリ/
├── {task_id}/
│   ├── {input_data_id}.json
│   ├── {input_data_id}/
│          ├── {annotation_id}............ 塗りつぶしPNG画像
```



### annotation import
アノテーションをプロジェクトにインポートします。
アノテーションのフォーマットは、Simpleアノテーション(v2)と同じフォルダ構成のzipファイルまたはディレクトリです。

```
ルートディレクトリ/
├── {task_id}/
│   ├── {input_data_id}.json
│   ├── {input_data_id}/
│          ├── {annotation_id}............ 塗りつぶしPNG画像
```

JSONフォーマットのサンプルをは以下の通りです。SimpleアノテーションのJSONフォーマットに対応しています。詳しくは https://annofab.com/docs/api/#section/Simple-Annotation-ZIP を参照してください。


```json
{
    "details": [
        {
            "label": "car",
            "data": {
                "left_top": {
                    "x": 878,
                    "y": 566
                },
                "right_bottom": {
                    "x": 1065,
                    "y": 701
                },
                "_type": "BoundingBox"
            },
            "attributes": {}
        },
        {
            "label": "road",
            "data": {
                "data_uri": "b803193f-827f-4755-8228-e2c67d0786d9",
                "_type": "SegmentationV2"
            },
            "attributes": {}
        },
        {
            "label": "weather",
            "data": {
                "_type": "Classification"
            },
            "attributes": {
                "sunny": true
            }
        }
    ]
}
```

以下のように`annotation_id`が指定されている場合、`annotation_id`もインポートされます。


```json
{
    "details": [
        {
            "label": "car",
            "annotation_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "data": {
                "left_top": {
                    "x": 878,
                    "y": 566
                },
                "right_bottom": {
                    "x": 1065,
                    "y": 701
                },
                "_type": "BoundingBox"
            },
            "attributes": {}
        },

```

アノテーションをインポートするには、事前に入力データ、タスク、アノテーション仕様を作成する必要があります。

タスクの状態が作業中/完了の場合はインポートしません。


```
# prj1にアノテーションをインポートします。すでにアノテーションが登録されてる場合はスキップします。
$ annofabcli annotation import --project_id prj1 --annotation simple-annotation.zip 

# prj1にアノテーションをインポートします。すでに存在するアノテーションを上書きます。
$ annofabcli annotation import --project_id prj1 --annotation simple-annotation.zip --overwrite
```

### annotation list_count
`task_id`または`input_data_id`で集約したアノテーションの個数を、CSV形式で出力します。
クエリのフォーマットは、[getAnnotationList API](https://annofab.com/docs/api/#operation/getAnnotationList)のクエリパラメータの`query`キー配下と同じです。
`label_name_en`(label_idに対応), `additional_data_definition_name_en`(additional_data_definition_idに対応) キーも指定できます。


```
# car ラベルのアノテーション個数を出力する(task_idで集約)
$ annofabcli annotation list_count --project_id prj1 \
 --annotation_query '{"label_name_en": "car"}'

# car ラベルのアノテーション個数を出力する(input_data_idで集約)
$ annofabcli annotation list_count --project_id prj1 \
 --annotation_query '{"label_name_en": "car"}' --gropu_by input_data_id

# task.txtに記載されたtask_idの一覧から、car ラベルのアノテーション個数を出力する
$ annofabcli annotation list_count --project_id prj1 \
 --annotation_query '{"label_name_en": "car"}'  --task_id file://task.txt

# carラベルの"occluded"チェックボックスがONのアノテーションの個数を出力する
$ annofabcli annotation list_count --project_id prj1 \
 --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}'

# carラベルの"type"ラジオボタン/セレクトボックスが"bus"であるアノテーションの個数を出力する
$ annofabcli annotation list_count --project_id prj1 \
 --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "choice_name_en": "bus"}]}'
```

#### task_idで集約したときの出力結果（CSV）

| task_id    | annotation_count |
|------------|------------------|
| sample_030 | 1                |
| sample_088 | 2                |


#### input_data_idで集約したときの出力結果（CSV）

| task_id    | input_data_id                        | annotation_count |
|------------|--------------------------------------|------------------|
| sample_030 | 5738d502-b0a0-4a82-9367-cceffd73cf57 | 1                |
| sample_093 | dd82cf3a-a38c-4a04-91e7-a4f1ce9af585 | 2                |


### annotation restore
[annotation dump](#annotation-dump) コマンドの出力結果から、アノテーション情報をリストアします。ただし、作業中/完了状態のタスク、または「過去に割り当てられていて現在の担当者が自分自身でない」タスクはリストアできません。


```
# `backup`ディレクトリに保存したアノテーション情報を、`prj1`プロジェクトにリストアする。
$annofabcli annotation restore --project_id prj1 --task_id file://task.txt --annotation backup-dir

# `backup`ディレクトリに保存したアノテーション情報の内、`task.txt`に記載されたタスクのアノテーション情報を、`prj1`プロジェクトにリストアする。
$ annofabcli annotation restore --project_id prj1 --task_id file://task.txt --annotation backup-dir
```



### annotation_specs history
アノテーション仕様の履歴一覧を出力します。

```
# prj1のアノテーション仕様の履歴一覧を出力する
$ annofabcli annotation_specs history --project_id prj1 
```



### annotation_specs list_label
アノテーション仕様のラベル情報を出力します。

```
# prj1のアノテーション仕様のラベル情報を、人間が見やすい形式（`--format text`）で出力する
$ annofabcli annotation_specs list_label --project_id prj1

# prj1のアノテーション仕様のラベル情報を、インデントされたJSONで出力する。
$ annofabcli annotation_specs list_label --project_id prj1 --format pretty_json

# 最新より１つ前の履歴である、アノテーション仕様を出力する。
$ annofabcli annotation_specs list_label --project_id prj1 --before 1

# history_idがXXXのアノテーション仕様を出力する。（history_idは、`annofabcli annotation_specs history`コマンドで取得する）
$ annofabcli annotation_specs list_label --project_id prj1 --history_id XXX


```

#### `--format text`の出力結果 
`--format text`の出力結果は、以下のフォーマットで出力されます。

```
label_id    label_type    label_name_ja    label_name_en
    attribute_id    attribute_type    attribute_name_ja    attribute_name_ja
        choice_id    choice_name_ja    choice_name_en
        ...
    ...
...
```

サンプルプロジェクトでコマンドを実行した結果は、以下の通りです。

```
15ba7932-24b9-4cf3-95bd-9bf6deede4fa	bounding_box	ネコ	Cat
	e6864d96-78fa-45f3-a786-6c8c900c92ae	flag	隠れ	occluded
	51e8c91f-5de1-450b-a0f3-94fec582f5ce	link	目のリンク	link-eye
	aff2855e-2e3d-47a2-8c27-c7652e4dfb2f	integer	体重	weight
	7e6a577a-3410-4c8a-9624-2904bb2e6666	comment	名前	name
	a63a0513-a96e-4c7c-8754-88a24fef9ca9	text	備考	memo
	649abf45-1ed7-459a-8282-a58228e9a302	tracking	object id	object id
c754f724-5f8c-48eb-81ec-ea77e55efee7	polyline	足	leg
f50aa88d-36c7-43f5-8728-247a49b4f4d8	point	目	eye
108ce1f7-217b-43e9-a407-8d0ac6aad87e	segmentation	犬	dog
2ffb4c74-106b-44ac-81ce-3c3df77518e0	segmentation_v2	人間	human
ded52dcb-bcd6-4e77-9626-61e546f635d0	polygon	鳥	bird
5ac0d7d5-6738-4c4b-a69a-cd583ff458e1	classification	気候	climatic
	896d7eeb-9c60-4fbf-b7c4-8f4209261049	choice	天気	weather
		c9615782-b872-4641-9be4-0fb4f905d966		晴	sunny
		553018a5-e594-4536-bc05-876fa6b48ed5		雨	rainy
	60caffa5-6300-4819-9a99-c43ce49008c2	select	気温	temparature
		89b3577d-a245-4b85-82ef-6569ecbf8ad7		10	10
		bdcd4d5b-cecc-4ec9-9038-d9284cd4f475		20	20
		9f3a0355-2cc8-412a-9129-3b62fa7b6ead		30	30
		2726336c-96d3-485b-9f96-7d4bcc97083b		40	40

```


### annotation_specs list_label_color
アノテーション仕様から、label_name(english)とRGBを対応付けたJSONを出力します。

```
$ annofabcli annotation_specs list_label_color --project_id prj1 
```

以下のJSONのような出力結果になります。

```json:出力結果
{
  "cat": [
    255,
    99,
    71
  ],
  "dog": [
    255,
    0,
    255
  ],
```




### filesystem write_annotation_image
アノテーションzip、またはそれを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成します。
以下のアノテーションが画像化対象です。
* 矩形
* ポリゴン
* 塗りつぶし
* 塗りつぶしv2


```
# アノテーションzipをダウンロードする。
$ annofabcli project download simple_annotation --project_id prj1 --output annotation.zip


# label_nameとRGBを対応付けたファイルを生成する
$ annofabcli annotation_specs list_label_color --project_id prj1 --output label_color.json


# annotation.zip から、アノテーション画像を生成する
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --image_size 1280x720 \
 --label_color file://label_color.json \
 --output_dir /tmp/output


# annotation.zip から、アノテーション画像を生成する。ただしタスクのステータスが"完了"で、task.txtに記載れたタスクのみ画像化する。
$ annofabcli filesystem write_annotation_image  --annotation annotation.zip \
 --image_size 1280x720 \
 --label_color file://label_color.json \
 --output_dir /tmp/output \
 --task_status_complete \
 --task_id file://task.txt
```

#### 出力結果（塗りつぶし画像）

![filesystem write_annotation_iamgeの塗りつぶし画像](readme-img/write_annotation_image-output.png)


### input_data delete
タスクに使われていない入力データを削除します。

```
# 入力データ input1, input2 を削除する
$ annofabcli input_data delete --project_id prj1 --input_data_id input1 input2

# `input_data_id.txt` ファイルに記載されている入力データを削除する
$ annofabcli input_data delete --project_id prj1 --input_data_id file://input_data_id.txt
```


### input_data list
入力データ一覧を出力します。

```
# input_data_nameが"sample"の入力データ一覧を出力する
$ annofabcli input_data list --project_id prj1 --input_data_query '{"input_data_name": "sample"}' 

# input_data_idが"id1", "id2"の入力データを取得する
$ annofabcli input_data list --project_id prj1 --input_data_id id1 id2

# 入力データの詳細情報（参照されているタスクのtask_id `parent_task_id_list`）も出力する
$ annofabcli input_data list --project_id prj1 --input_data_query '{"input_data_name": "sample"}' --add_details

```


#### 出力結果（CSV）


| etag                             | input_data_id                        | input_data_name                   | input_data_path                                                                                                                                                                 | original_input_data_path                                                                                                                                                        | original_resolution | project_id                           | resized_resolution | sign_required | task_id_list   | updated_datetime              | url                                                                                                                                                                        |
|----------------------------------|--------------------------------------|-----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|--------------------------------------|--------------------|---------------|----------------|-------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| a43717273502b67a1989c9b25e252cde | 3c8d8f15-14f0-467a-a8fe-562cbbccf08a | val.zip/val/9a70bdec-1504e338.jpg | s3://example.com/example | s3://example.com/example |                     | 58a2a621-7d4b-41e7-927b-cdc570c1114a |                    | False         | ['sample_247'] | 2019-04-19T16:36:17.846+09:00 | https://annofab.com/projects/example/input_data/example |




### input_data list_merged_task
タスク一覧と結合した入力データ一覧のCSVを出力します。
動画プロジェクトで、各タスクの動画時間を調べる際などに利用できます。

```
# prj1の入力データ全件ファイル、タスク全件ファイルをダウンロードして、マージしたCSVを出力する
$ annofabcli input_data list_merged_task --project_id prj1 --output input_data.csv

# prj1の入力データ全件ファイル、タスク全件ファイルの最新版をダウンロードして、マージしたCSVを出力する
$ annofabcli input_data list_merged_task --project_id prj1 --output input_data.csv --latest

# 入力データ全件ファイル、タスク全件ファイルのJSONから、マージしたCSVを出力する
$ annofabcli input_data list_merged_task --input_data_json input_data.json --task_json task.json --output input_data.csv
```


### input_data put
CSVに記載された入力データ情報やzipファイルを、入力データとして登録します。

#### CSVに記載された入力データ情報を、入力データとして登録

* ヘッダ行なし
* カンマ区切り
* 1列目: input_data_name. 必須
* 2列目: input_data_path. 必須. 先頭が`file://`の場合、ローカルのファイルを入力データとしてアップロードします。
* 3列目: input_data_id. 省略可能。省略した場合UUIDv4になる。
* 4列目: sign_required. 省略可能. `true` or `false`

CSVのサンプル（`input_data.csv`）です。

```
data1,s3://example.com/data1,id1,
data2,s3://example.com/data2,id2,true
data3,s3://example.com/data3,id3,false
data4,https://example.com/data4,,
data5,file://sample.jpg,,
data6,file:///tmp/sample.jpg,,
```


```
# input_data.csvに記載されている入力データを登録する。すでに入力データが存在する場合はスキップする。
$ annofabcli input_data put --project_id prj1 --csv input_data.csv

# input_data.csvに記載されている入力データを登録する。すでに入力データが存在する場合は上書きする。
$ annofabcli input_data put --project_id prj1 --csv input_data.csv --overwrite

# input_data.csvに記載されている入力データを、並列処理で登録する（`--yes`オプションが必要）。
$ annofabcli input_data put --project_id prj1 --csv input_data.csv --parallelism 2 --yes
```


`input_data list`コマンドを使えば、プロジェクトに既に登録されている入力データからCSVを作成できます。

```
$ annofabcli input_data list --project_id prj1 --input_data_query '{"input_data_name": "sample"}'  \
 --format csv --output input_data.csv \
 --csv_format '{"columns": ["input_data_name","input_data_path", "input_data_id", "sign_required"], "header":false}' 
```


#### zipファイルを入力データとして登録


```
# 画像や動画が格納されたinput_data.zipを、入力データとして登録する
$ annofabcli input_data put --project_id prj1 --zip input_data.zip

# zipファイルを入力データとして登録し、入力データの登録が完了するまで待つ。
$ annofabcli input_data put --project_id prj1 --zip input_data.zip --wait

# zipファイルを入力データとして登録する。そのときinput_data_nameを`foo.zip`にする。
$ annofabcli input_data put --project_id prj1 --zip input_data.zip --input_data_name_for_zip foo.zip

```



### input_data update_metadata
入力データのメタデータを更新します。

```
# `input_data.txt`に記載されている入力データIDに対して、入力データのメタデータを '{"foo":"bar"}' に変更します。
$ annofabcli input_data update_metadata --project_id prj1 --input_data_id --file://input_data.txt --metadata '{"foo":"bar"}'

```


### inspection_comment list
検査コメント一覧を出力します。

```
# task1, task2の検査コメント一覧を、CSVで出力する
$ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2

# タブ区切りの"out.tsv"を出力する
$ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2 \
 --format csv --csv_format '{"sep":"\t"}'  --output out.tsv

# JSONで出力する
$ annofabcli inspection_comment list --project_id prj1 --task_id file://task.txt --format json

# 検査コメント情報が記載されたファイルを元にして、検査コメント一覧を出力します
# 検査コメント情報が記載されたファイルは、`$ annofabcli project download inspection_comment`コマンドで取得できます。
$ annofabcli inspection_comment list --project_id prj1 --inspection_comment_json inspection_comment.json

# 返信コメントを除外した検査コメント一覧を出力します
$ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2 --exclude_reply

# 返信コメントのみの一覧を出力します
$ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2 --only_reply


```

#### 出力結果（CSV）

| project_id                           | task_id    | input_data_id                        | inspection_id                        | phase      | phase_stage | commenter_account_id                 | annotation_id                        | label_id                             | data                                  | parent_inspection_id | phrases | comment | status          | created_datetime              | updated_datetime              | commenter_user_id | commenter_username | phrase_names_en | phrase_names_ja | label_name_en | label_name_ja | input_data_index |
|--------------------------------------|------------|--------------------------------------|--------------------------------------|------------|-------------|--------------------------------------|--------------------------------------|--------------------------------------|---------------------------------------|----------------------|---------|---------|-----------------|-------------------------------|-------------------------------|-------------------|--------------------|-----------------|-----------------|---------------|---------------|------------------|
| 58a2a621-7d4b-41e7-927b-cdc570c1114a | sample_180 | bf6b4790-cdb8-4d4d-85bb-08550934ed61 | 5f096677-67e4-4e75-9eac-bbd8ac9694d9 | inspection | 1           | 12345678-abcd-1234-abcd-1234abcd5678 | 8aff181e-9df4-4c66-8fb2-10596c686d5c | 8aff181e-9df4-4c66-8fb2-10596c686d5c | {'x': 358, 'y': 48, '_type': 'Point'} |                      | []      | 枠がずれています     | error_corrected | 2019-07-26T17:41:16.626+09:00 | 2019-08-01T10:57:45.639+09:00 | user_id   | username          | []              | []              | car           | car           | 0                |


### inspection_comment list_unprocessed
未処置の検査コメント一覧を出力します。

```
# 未処置の検査コメント一覧を出力する
$ annofabcli inspection_comment list_unprocessed --project_id prj1 --task_id file://task.txt

# 未処置で、user1が"hoge"とコメントした検査コメント一覧を出力する
$ annofabcli inspection_comment list_unprocessed  --project_id prj1 --task_id file://task.txt \
 --inspection_comment "hoge" --commenter_user_id user1 --format pretty_json --output inspection.json

# 検査コメント情報が記載されたファイルを元にして、検査コメント一覧を追加します
$ annofabcli inspection_comment list_unprocessed --project_id prj1 --inspection_comment_json inspection_comment.json
```


### instruction copy
作業ガイドを別のプロジェクトにコピーします。


```
# prj1の作業ガイドをprj2にコピーする
$ annofabcli instruction copy prj1 prj2
```



### instruction upload
HTMLファイルを作業ガイドとして登録します。
img要素のsrc属性がローカルの画像を参照している場合（http, https, dataスキーマが付与されていない）、画像もアップロードします。

`instruction.html`の中身。

```html
<html>
<head></head>
<body>
作業ガイドのサンプル
<img src="lena.png">
</body>
</html>
```

```
$ annofabcli instruction upload --project_id prj1 --html instruction.html
```


#### Confluenceのページを作業ガイド用にHTMLとして保存する場合
1. Confluenceのエクスポート機能で、ページをエクスポートする。
    * HTMLファイルと添付画像が含まれたzipファイルをダウンロードする。
2. エクスポートしたHTMLのスタイルを、style属性に反映させる。AnnoFabの作業ガイドには、スタイルシートを登録できないため。
    1. エクスポートしたファイルをChromeで開く
    2. Chrome開発ツールのConfoleタブで以下のJavaScriptを実行して、全要素のborder, color, backgroundスタイルを、style属性に反映させる

        ```js
        elms = document.querySelectorAll("body *");
        for (let e of elms) {
            s = window.getComputedStyle(e);
            e.style.background = s.background;
            e.style.color = s.color;
            e.style.border = s.border;
        }
        ```
    3. Chrome開発ツールのElementタブで、html要素をコピー(Copy outerHTML)して、HTMLファイルを上書きする


### job delete
ジョブを削除します。
削除対象のjob_idは`annofabcli job list`コマンドで確認できます。

```
# アノテーション更新のジョブを削除します。
$ annofabcli job delete --project_id prj1 --job_type gen-annotation --job_id 12345678-abcd-1234-abcd-1234abcd5678
```


### job list
ジョブ一覧を出力します。

```
# アノテーション更新のジョブ一覧を取得します（最新のジョブ1個のみ）
$ annofabcli job list --project_id prj1 --job_type gen-annotation

# タスク作成のジョブ一覧を取得します（最大200個）
$ annofabcli job list --project_id prj1 --job_type gen-tasks --job_query '{"limit": 200}'

```



### job list_last
複数のプロジェクトに対して、最新のジョブを出力します。

```
# prj1, prj2に対して、「アノテーション更新」のジョブを出力します。
$ annofabcli job list_last --project_id prj1 prj2 --job_type gen-annotation

# 組織 org1配下のプロジェクト（進行中で、自分自身が所属している）に対して、「タスク全件ファイル更新」のジョブを出力します。
$ annofabcli job list_last --organization org1 --job_type gen-tasks-list

# アノテーションの最終更新日時を、タスクの最終更新日時と比較して出力します。
$ annofabcli job list_last --project_id prj1 --job_type gen-annotation --add_details \
 --csv_format '{"columns": ["project_id","project_title","job_status","updated_datetime", "task_last_updated_datetime"]}' 

```


### labor list_worktime_by_user

ユーザごとに作業予定時間、作業実績時間を出力します。

```
# 組織org1, org2に対して、user1, user2の作業時間を集計します。
$ annofabcli labor list_worktime_by_user --organization org1 org2 --user_id user1 user2 \
 --start_date 2019-10-01 --end_date 2019-10-31 --output_dir /tmp/output

# プロジェクトprj1, prj2に対して作業時間を集計します。集計対象のユーザはプロジェクトに所属するメンバです。
$ annofabcli labor list_worktime_by_user --project_id prj1 prj2 --user_id user1 user2 \
 --start_date 2019-10-01 --end_date 2019-10-31 --output_dir /tmp/output


# user.txtに記載されているユーザの予定稼働時間も一緒に出力します。
$ annofabcli labor list_worktime_by_user --project_id prj1 prj2 --user_id file://user.txt \
 --start_month 2019-10 --end_month 2019-11 --add_availability --output_dir /tmp/output

```


### organization_member list
組織メンバ一覧を出力します。

```
# 組織org1の組織メンバ一覧を出力します。
$ annofabcli organization_member list --organization org1

```



### project cooy
プロジェクトをコピーして（アノテーション仕様やメンバーを引き継いで）、新しいプロジェクトを作成します。



```
# prj1 プロジェクトをコピーして、"prj2-title"というプロジェクトを作成する
$ annofabcli project copy --project_id prj1 --dest_title "prj2-title"


# prj1 プロジェクトをコピーして、"prj2"というプロジェクトIDのプロジェクトを作成する。
# コピーが完了するまで待つ(処理を継続する)
$ annofabcli project copy --project_id prj1 --dest_title "prj2-title" --dest_project_id prj2 \
 --wait


# prj1 プロジェクトの入力データと、タスクをコピーして、"prj2-title"というプロジェクトを作成する
$ annofabcli project copy --project_id prj1 --dest_title "prj2-title" --copy_inputs --copy_tasks


```




### project diff
プロジェクト間の差分を、以下の項目について表示します。差分がない場合、標準出力は空になります。
* アノテーション仕様のラベル情報
* 定型指摘
* プロジェクトメンバ
* プロジェクトの設定


```
# すべての差分
$ annofabcli project diff  prj1 prj2

# アノテーション仕様のラベル情報の差分
$ annofabcli project diff prj1 prj2 --target annotation_labels

# 定型指摘の差分
$ annofabcli project diff prj1 prj2 --target inspection_phrases

# プロジェクトメンバの差分
$ annofabcli project diff  prj1 prj2 --target members

# プロジェクト設定の差分
$ annofabcli project diff  prj1 prj2 --target settings

```



プロジェクト間の差分は、以下のように出力されます。
`dict`型の差分は、[dictdiffer](https://dictdiffer.readthedocs.io/en/latest/)のフォーマットで出力します。

```
=== prj1_title1(prj1) と prj1_title2(prj2) の差分を表示
=== プロジェクトメンバの差分 ===
プロジェクトメンバは同一
=== プロジェクト設定の差分 ===
プロジェクト設定は同一
=== 定型指摘の差分 ===
定型指摘は同一
=== アノテーションラベル情報の差分 ===
ラベル名(en): car は差分あり
[('change', 'color.red', (4, 0)),
 ('change', 'color.green', (251, 255)),
 ('change', 'color.blue', (171, 204))]
ラベル名(en): bike は同一
```



### project download
プロジェクトに対して、タスクや検査コメント、アノテーションなどをダウンロードします。
ダウンロード対象は以下の通りです。
* すべてのタスクが記載されたJSON
* すべての入力データが記載されたJSON
* すべての検査コメントが記載されたJSON
* すべてのタスク履歴イベントが記載されたJSON
* すべてのタスク履歴イベントが記載されたJSON（非推奨）
* Simpleアノテーションzip
* Fullアノテーションzip（非推奨）


```
# タスクの全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project download task --project_id prj1 --output task.json

# 入力データのすべてが記載されたJSONファイルをダウンロードする
$ annofabcli project download input_data --project_id prj1 --output input_data.json

# 検査コメントの全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project  download inspection_comment --project_id prj1 --output inspection_comment.json

# タスク履歴イベントの全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project download task_history --project_id prj1 --output task_history.json

# Simpleアノテーションのzipファイルをダウンロードする
$ annofabcli project download simple_annotation --project_id prj1 --output simple_annotation.zip

# 最新のSimpleアノテーションのzipファイルをダウンロードする
$ annofabcli project download simple_annotation --project_id prj1 --output simple_annotation.zip --latest

# 最新のタスク全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project download task --project_id prj1 --output task.json --latest

# アノテーションの最新化を最大60分(60秒間隔で最大60回アクセス)待つ
$ annofabcli project download simple_annotation --project_id prj1  58a2a621-7d4b-41e7-927b-cdc570c1114a --output simple_annotation.zip --latest \
 --wait_options '{"interval":60, "max_tries":60}' 
```


### project list
プロジェクト一覧を出力します。

```
# org1配下のプロジェクトで、user1が所属する進行中のプロジェクト一覧を出力する。
$ annofabcli project list --organization org1 --project_query '{"status": "active", "user_id": "user1}'

# prj1, prj2のプロジェクト一覧を出力する
$ annofabcli project list --project_id prj1 prj2
```


### project update_annotation_zip
アノテーションzipを更新します。

```
# prj1, prj2のアノテーションzipを更新します。更新する必要がなければ更新しません。
$ annofabcli project update_anotation_zip --project_id prj1 prj2

# prj1, prj2のアノテーションzipを更新します。更新する必要がなくても常に更新します。
$ annofabcli project update_anotation_zip --project_id prj1 prj2 --force

# prj1, prj2のアノテーションzipを更新して、すべてのプロジェクトの更新が完了するまで待ちます
$ annofabcli project update_anotation_zip --project_id prj1 prj2 --wait

# アノテーションzipの更新が完了するまで待つ処理を並列で実行します。
$ annofabcli project update_anotation_zip --project_id prj1 prj2 --wait --parallelism 4
```



### project_member change
複数のプロジェクトメンバに対して、メンバ情報を変更します。ただし、自分自身は変更できません。

```
# user1, user2のロールを"worker"（アノテータ）に変更する
$ annofabcli project_member change --project_id prj1 --user_id user1 user2 --role worker

# `user_id.txt`に記載されたuser_idに対して、抜取検査率、抜取受入率を指定する
$ annofabcli project_member change --project_id prj1 --user_id file://user_id.txt \
 --member_info '{"sampling_inspection_rate": 10, "sampling_acceptance_rate": 20}'

# すべてのユーザに対して、抜取検査率を未設定にする
$ annofabcli project_member change --project_id prj1 --all_user \
 --member_info '{"sampling_inspection_rate": null}'

```



### project_member copy
プロジェクトメンバを別のプロジェクトにコピーします。

```
# prj1のメンバをprj2にコピーする。
$ annofabcli project_member copy prj1 prj2

# prj1のメンバをprj2にコピーする。prj2にしか存在しないメンバは削除される。
$ annofabcli project_member copy prj1 prj2 --delete_dest
```



### project_member delete
複数のプロジェクトからユーザを削除します。

```
# ORG組織配下のすべてのプロジェクトから、user1, user2を削除する
$ annofabcli project_member delete --user_id user1 user2  --organization ORG

# prj1, prj2のプロジェクトからuser1をaccepterロールで招待する
$ annofabcli project_member invite --user_id user1  --project_id prj1 prj2
```



### project_member invite
複数のプロジェクトに、ユーザを招待します。

```
# ORG組織配下のすべてのプロジェクトに、user1, user2をownerロールで招待する
$ annofabcli project_member invite --user_id user1 user2 --role owner --organization ORG

# prj1, prj2のプロジェクトに、user1をaccepterロールで招待する
$ annofabcli project_member invite --user_id user1 --role accepter --project_id prj1 prj2
```


### project_member list
プロジェクトメンバ一覧を出力します。

```
# ORG組織配下のすべてのプロジェクトのプロジェクトメンバ一覧を出力する
$ annofabcli project_member list --organization ORG

# prj1, prj2のプロジェクトのプロジェクトメンバ一覧を出力する
$ annofabcli project_member list --project_id prj1 prj2
```

#### 出力結果（CSV）

| project_id                           | account_id                           | user_id         | username  | member_status | member_role | updated_datetime              | created_datetime              | sampling_inspection_rate | sampling_acceptance_rate | project_title                |
|--------------------------------------|--------------------------------------|-----------------|-----------|---------------|-------------|-------------------------------|-------------------------------|--------------------------|--------------------------|------------------------------|
| 12345678-abcd-1234-abcd-1234abcd5678 | 12345678-abcd-1234-abcd-1234abcd5678 | user_id | username | active        | owner       | 2019-09-10T14:51:00.908+09:00 | 2019-04-19T16:29:41.069+09:00 |                          |                          | sample_project |


### project_member put
CSVに記載されたユーザを、プロジェクトメンバとして登録します。

members.csvの中身は以下の通りです。

* ヘッダ行なし
* カンマ区切り
* 1列目: user_id. 必須
* 2列目: member_role. 必須.  `owner`, `worker`, `accepter`, `training_data_user` のいずれか。
* 3列目: sampling_inspection_rate. 省略可能。
* 4列目: sampling_acceptance_rate. 省略可能。


```
user1,worker
user2,accepter,80,40
```


```
# CSVに記載れたユーザを、prj1プロジェクトのメンバとして登録します。
$ annofabcli project_member put --project_id prj1 --csv members.csv

# CSVに記載れたユーザを、prj1プロジェクトのメンバとして登録します。csvに記載されていないユーザは削除します。
$ annofabcli project_member put --project_id prj1 --csv members.csv --delete
```

### statistics list_annotation_count
各ラベル、各属性値のアノテーション数を、タスクごと/入力データごとに出力します。
`--annotation`にはAnnoFabからダウンロードしたSimpleアノテーションzipのパスを渡します。指定しない場合はAnnoFabからダウンロードします。
出力結果には以下のファイルが含まれています。
* `labels_count.csv`：各ラベルのアノテーション数
* `attirbutes_count.csv`：各属性値のアノテーション数（ただし属性の種類がチェックボックス、ラジオボタン、セレクトボックスの属性のみが対象）


```
# タスクごとにアノテーション数を、output ディレクトリに出力
$ annofabcli statistics list_annotation_count --project_id prj1 --output_dir output --annotation annotataion.zip

# 入力データごとにアノテーション数を、output ディレクトリに出力。アノテーション情報はAnnoFabからダウンロードする
$ annofabcli statistics list_annotation_count --project_id prj1 --output_dir output --group_by input_data_id

```


### statistics list_by_date_user

タスク数や作業時間などの情報を、日ごとユーザごとに出力します。

```
$ annofabcli statistics list_by_date_user --project_id prj1 --output data.csv

```



### statistics list_cumulative_labor_time
タスクフェーズ別の累積作業時間をCSV形式で出力します。

```
$ annofabcli statistics list_cumulative_labor_time --project_id prj1 --output stat.csv
```

### statistics list_task_progress
タスク進捗状況をCSV形式で出力します。

```
$ annofabcli statistics list_task_progress --project_id prj1 --output stat.csv
```

### statistics summarize_task_count
タスクのフェーズ、ステータス、ステップごとにタスク数を、CSV形式で出力します。
「1回目の教師付」と「2回目の教師付」を区別して集計されます。


```
# prj1のタスク数を出力します。ダウンロードしたタスク全件ファイルを元にして出力します（AM02:00頃更新）。
$ annofabcli statistics summarize_task_count --project_id prj1 --output task-count.csv

# `annofabcli project download task`でダウンロードした`task.json`を元にして、タスク数を出力します。
$ annofabcli statistics summarize_task_count --project_id prj1 --task_json task.json --output task-count.csv

```

以下のようなCSVが出力されます。

```csv
step,phase,phase_stage,simple_status,task_count
1,annotation,1,not_started,3761
1,annotation,1,working_break_hold,30
1,acceptance,1,not_started,1861
1,acceptance,1,working_break_hold,20
2,annotation,1,not_started,225
2,annotation,1,working_break_hold,3
2,acceptance,1,not_started,187
5,acceptance,1,not_started,1
,acceptance,1,complete,3000
```


* step：何回目のフェーズか
* simple_status：タスクステータスを簡略化したもの
    * not_started：未着手
    * working_break_hold：作業中か休憩中か保留中
    * complete：完了

「一度も作業されていない教師付未着手」のタスク数は、先頭行（step=1, phase=annotation, simple_status=not_started）のtask_countから分かります。


### statistics summarize_task_count_by_task_id
task_idのプレフィックスごとに、タスク数をCSV形式で出力します。
task_idは`{prefix}_{連番}`のようなフォーマットを想定しています。


```
# prj1のタスク数を出力します。ダウンロードしたタスク全件ファイルを元にして出力します（AM02:00頃更新）。
$ annofabcli statistics summarize_task_count_by_task_id --project_id prj1 --output task-count.csv

# `annofabcli project download task`でダウンロードした`task.json`を元にして、タスク数を出力します。
$ annofabcli statistics summarize_task_count_by_task_id --project_id prj1 --task_json task.json --output task-count.csv

```

以下のようなCSVが出力されます。

```csv
task_id_prefix,complete,on_hold,annotation_not_started,inspection_not_started,acceptance_not_started,other,sum
20200401,10,0,0,0,0,0,10
20200501,10,1,4,0,1,4,20
```

各列
* annotation_not_started: 教師付フェーズが一度も作業されていないタスク数
* inspection_not_started: 検査フェーズが一度も作業されていないタスク数
* acceptance_not_started: 受入フェーズが一度も作業されていないタスク数
* other: 休憩中、作業中、
* simple_status：タスクステータスを簡略化したもの
    * not_started：未着手
    * working_break_hold：作業中か休憩中か保留中
    * complete：完了

「一度も作業されていない教師付未着手」のタスク数は、先頭行（step=1, phase=annotation, simple_status=not_started）のtask_countから分かります。


### statistics summarize_task_count_by_user
ユーザごとに担当しているタスク数をCSV形式で出力します。


```
# prj1のタスク数を出力します。ダウンロードしたタスク全件ファイルを元にして出力します（AM02:00頃更新）。
$ annofabcli statistics summarize_task_count_by_user --project_id prj1 --output task-count.csv

# `annofabcli project download task`でダウンロードした`task.json`を元にして、タスク数を出力します。
$ annofabcli statistics summarize_task_count_by_task_id --project_id prj1 --task_json task.json --output task-count.csv

```

以下のようなCSVが出力されます。

```csv
task_id_prefix,complete,on_hold,annotation_not_started,inspection_not_started,acceptance_not_started,other,sum
20200401,10,0,0,0,0,0,10
20200501,10,1,4,0,1,4,20
```

各列
* annotation_not_started: 教師付フェーズが一度も作業されていないタスク数
* inspection_not_started: 検査フェーズが一度も作業されていないタスク数
* acceptance_not_started: 受入フェーズが一度も作業されていないタスク数
* other: 休憩中、作業中、
* simple_status：タスクステータスを簡略化したもの
    * not_started：未着手
    * working_break_hold：作業中か休憩中か保留中
    * complete：完了

「一度も作業されていない教師付未着手」のタスク数は、先頭行（step=1, phase=annotation, simple_status=not_started）のtask_countから分かります。


### statistics visualize
統計情報を可視化します。

```
# prj1の統計情報を可視化したファイルを、/tmp/outputに出力する
$ annofabcli statistics visualize --project_id prj1 --output_dir /tmp/output

# statusがcompleteのタスクを統計情報を可視化したファイルを、/tmp/outputに出力する
$ annofabcli statistics visualize --project_id prj1 --output_dir /tmp/output \
  --task_query '{"status": "complete"}' 

# アノテーションzipを更新してから、アノテーションzipをダウンロードします。
$ annofabcli statistics visualize --project_id prj1 --output_dir /tmp/output --update_annotation


# WebAPIを実行せずに、作業ディレクトリ（デフォルトは`$XDG_CACHE_HOME/annofabcli`）内のファイルを参照して、統計情報を可視化する。
$ annofabcli statistics visualize --project_id prj1 --not_update

```

### supplementary list
補助情報一覧を出力します。

```
# input_data_idが"id1", "id2"に紐づく補助情報一覧を出力します。
$ annofabcli supplementary list --project_id prj1 --input_data_id id1 id2
```

### supplementary put
CSVに記載された補助情報を登録します。

supplementary_data_id（省略時は supplementary_data_number）が一致する補助情報が既に存在する場合は、スキップまたは上書きします。

* ヘッダ行なし
* カンマ区切り
* 1列目: input_data_id. 必須
* 2列目: supplementary_data_number. 必須
* 3列目: supplementary_data_name. 必須
* 4列目: supplementary_data_path. 必須. 先頭が`file://`の場合、ローカルのファイルを入力データとしてアップロードします。
* 5列目: supplementary_data_id. 省略可能。省略した場合UUIDv4になる。
* 6列目: supplementary_data_type. 省略可能. `image` or `text`

CSVのサンプル（`supplementary_data.csv`）です。

```
input1,1,data1-1,s3://example.com/data1,id1,
input1,2,data1-2,s3://example.com/data2,id2,image
input1,3,data1-3,s3://example.com/data3,id3,text
input2,1,data2-1,https://example.com/data4,,
input2,2,data2-2,file://sample.jpg,,
input2,3,data2-3,file:///tmp/sample.jpg,,
```


```
# supplementary_data.csvに記載されている補助情報を登録する。すでに補助情報が存在する場合はスキップする。
$ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv

# supplementary_data.csvに記載されている補助情報を登録する。すでに補助情報が存在する場合は上書きする。
$ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv --overwrite

# supplementary_data.csvに記載されている補助情報を、並列処理で登録する（`--yes`オプションが必要）。
$ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv --parallelism 2 --yes
```


`supplementary list`コマンドを使えば、プロジェクトに既に登録されている補助情報からCSVを作成できます。

```
$ annofabcli supplementary list --project_id prj1 --input_data_id id1 id2 \
 --format csv --output supplementary_data.csv \
 --csv_format '{"columns": ["input_data_id", "supplementary_data_number", "supplementary_data_name", "supplementary_data_path", "supplementary_data_id", "supplementary_data_type"], "header":false}' 
```



### task cancel_acceptance
受け入れ完了タスクに対して、受け入れ取り消しにします。
アノテーションルールを途中で変更したときなどに、利用します。


```
# prj1プロジェクトのタスクを、受け入れ取り消しにする。最後に受入を担当したユーザに割り当てる
$ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt

# prj1プロジェクトのタスクを、受け入れ取り消しにする。ユーザuser1に割り当てる。
$ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt --assigned_acceptor_user_id user1

# prj1プロジェクトのタスクを、受け入れ取り消しにする。担当者は未割り当て
$ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt --not_assign


```


### task change_operator
タスクの担当者を変更します。


```
# 指定されたタスクの担当者を 'user1' に変更する。
$ annofabcli task change_operator --project_id prj1 --task_id file://task.txt --user_id uer1

# 指定されたタスクの担当者を未割り当てに変更する。
$ annofabcli task change_operator --project_id prj1 --task_id file://task.txt --not_assign

# 教師付フェーズが未着手のタスクのみ、担当者を変更する
$ annofabcli task change_operator --project_id prj1 --task_id file://task.txt --not_assign --task_query '{"status:"not_started", "phase"}'

```


### task complete
タスクを完了状態にして次のフェーズに進めます。（教師付の提出、検査/受入の合格） 。
教師付フェーズを完了にする場合は、未回答の検査コメントに対して返信することができます（未回答の検査コメントに対して返信しないと、タスクを提出できないため）。
検査/受入フェーズを完了する場合は、未処置の検査コメントを対応完了/対応不要状態に変更できます（未処置の検査コメントが残っている状態では、タスクを合格にできないため）。


```
# 教師付フェーズのタスクを提出して、次のフェーズに進めます。未回答の検査コメントがある場合は、スキップします。
$ annofabcli task complete --project_id prj1 --task_id file://task.txt --phase annotation

# 教師付フェーズのタスクを提出して、次のフェーズに進めます。未回答の検査コメントには「対応しました」と返信します。
$ annofabcli task complete --project_id prj1 --task_id file://task.txt --phase annotation --reply_comment "対応しました"

# 検査フェーズでステージ2のタスクを合格にして、次のフェーズに進めます。未処置の検査コメントがある場合は次に進めます
$ annofabcli task complete --project_id prj1 --task_id file://task.txt --phase inspection --phase_stage 2

# 受入フェーズのタスクを合格にして、次のフェーズに進めます。未処置の検査コメントは「対応不要」状態にします。
$ annofabcli  task complete --project_id prj1 --task_id file://task.txt --phase acceptance \
 --inspection_status no_correction_required 
```



### task delete
タスクを削除します。ただし、作業中/完了状態のタスクは削除できません。デフォルトでは、アノテーションが付与されているタスクは削除できません。
アノテーションの削除には [annotation delete](#annotation-delete) コマンドを利用できます。

```
# task_id.txtに記載されたtask_idのタスクを削除します。
$ annofabcli task delete --project_id prj1 --task_id file://task_id.txt

# アノテーションが付与されているかどうかにかかわらず、タスクを削除します。
$ annofabcli task delete --project_id prj1 --task_id file://task_id.txt --force

```


### task list
タスク一覧を出力します。

```
# 受入フェーズで、"usr1"が担当しているタスクの一覧を出力する
$ annofabcli task list --project_id prj1 --task_query '{"user_id": "usr1","phase":"acceptance"}' 

# task_id"id1", "id2"のタスクを取得する
$ annofabcli task list --project_id prj1 --task_id id1 id2

# 休憩中で、過去の担当者が"usr1"であるタスクの一覧を出力する。task.jsonファイルにJSON形式で出力する。
$ annofabcli task list --project_id prj1 \
 --task_query '{"previous_user_id": "usr1","status":"break"}' --format json --out task.json

# 差し戻されたタスクのtask_idを出力する
$ annofabcli task list --project_id prj1 --task_query '{"rejected_only": true}' --format task_id_list 

# タスク情報が記載されたファイルを元にして、タスク一覧を出力します
# タスク情報が記載されたファイルは、`$ annofabcli project download task`コマンドで取得できます。
$ annofabcli task list --project_id prj1 --task_json task.json


```

#### 出力結果

| project_id                           | task_id                                | phase      | phase_stage | status      | input_data_id_list                       | account_id                           | histories_by_phase                                                                                                                                       | work_time_span | number_of_rejections | started_datetime              | updated_datetime              | sampling | user_id         | username  | worktime_hour       | number_of_rejections_by_inspection | number_of_rejections_by_acceptance |
|--------------------------------------|----------------------------------------|------------|-------------|-------------|------------------------------------------|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|----------------------|-------------------------------|-------------------------------|----------|-----------------|-----------|---------------------|------------------------------------|------------------------------------|
| 12345678-abcd-1234-abcd-1234abcd5678 | 12345678-abcd-1234-abcd-1234abcd5678   | annotation | 1           | break       | ['12345678-abcd-1234-abcd-1234abcd5678'] | 12345678-abcd-1234-abcd-1234abcd5678 | [{'account_id': '12345678-abcd-1234-abcd-1234abcd5678', 'phase': 'annotation', 'phase_stage': 1, 'user_id': 'user_id1', 'username': 'username1'}] | 539662         | 0                    | 2019-05-08T13:53:21.338+09:00 | 2019-05-08T14:15:07.318+09:00 |          | user_id1 | user_name2 | 0.14990611111111113 | 0                                  | 0                                  |





### task list_added_task_history
タスク履歴情報（フェーズごとの作業時間、担当者、開始日時）を加えたタスク一覧をCSV形式で出力します。
最初に教師付を開始した日時や担当者を調べるときなどに利用できます。


```
# prj1のタスク全件ファイル、タスク履歴全件ファイルをダウンロードして、タスク一覧のCSVを出力する
$ annofabcli task list_added_task_history --project_id prj1 --output task.csv

# prj1のタスク全件ファイルの最新版をダウンロードして、タスク一覧のCSVを出力する。タスク履歴全件ファイルはWebAPIの都合上最新化できません。
$ annofabcli task list_added_task_history --project_id prj1 --output task.csv --latest

# タスク全件ファイルJSON、タスク履歴全件ファイルJSONを参照して、タスク一覧のCSVを出力する
$ annofabcli task list_added_task_history --project_id prj1 --output task.csv --task_json task.json --task_history_json task_history.json
```

### task list_task_history
タスク履歴の一覧を出力します。


```
# prj1の全タスクのタスク履歴の一覧を、CSV形式で出力する
$ annofabcli task list_task_history --project_id prj1 --output task_history.csv

```


### task put
タスクを作成します。

### CSVファイルに記載された情報を元にタスクを作成する場合
CSVに記載された情報を元に、タスクを登録します。
CSVのフォーマットは以下の通りです。

```
1列目: task_id
2列目: 空欄（どんな値でもよい）
3列目: input_data_id
```

CSVのサンプル（`task.csv`）です。

```
task_1,,ca0cb2f9-fec5-49b4-98df-dc34490f9785
task_1,,5ac1987e-ca7c-42a0-9c19-b5b23a41836b
task_2,,4f2ae4d0-7a38-4f9a-be6f-170ba76aba73
task_2,,45ac5852-f20c-4938-9ee9-cc0274401df7
```

```
# prj1に、タスク登録処理を投入する。
$ annofabcli task put --project_id prj1 --csv task.csv

# prj1に、タスク登録処理を投入する。タスク登録が完了するまで待つ.
$ annofabcli task put --project_id prj1 --csv task.csv --wait
```

#### 1つのタスクに割り当てる入力データの個数を指定してタスクを作成する場合
1つのタスクに割り当てる入力データの個数などの情報を、`--by_count`引数に指定します。
フォーマットは [initiateTasksGeneration](https://annofab.com/docs/api/#operation/initiateTasksGeneration) APIのリクエストボディ `task_generate_rule` を参照してください。

```
# 「タスクIDのプレフィックスを"sample"、1タスクの入力データ数を10個」でタスクを作成する。
$ annofabcli task  put --project_id prj1 --by_count '{"task_id_prefix":"sample","input_data_count":10}' 

# 「タスクIDのプレフィックスを"sample"、1タスクの入力データ数を10個、入力データ名を降順、
# 既にタスクに使われている入力データも利用」でタスクを作成し、タスク作成が完了するまで待つ
$ annofabcli task  put --project_id prj1 --by_count '{"task_id_prefix":"sample","input_data_count":10, \
 "input_data_order":"random", "allow_duplicate_input_data":true}' --wait
```


### task reject
タスクを強制的に差し戻します。差し戻す際に検査コメントを付与することもできます。検査コメントは、画像プロジェクトならばタスク内の先頭の画像の左上(`x=0,y=0`)に、動画プロジェクトなら動画の先頭（`start=0, end=100`)に付与します。
この差戻しは差戻しとして扱われず、抜取検査・抜取受入のスキップ判定に影響を及ぼしません。

タスクの状態・フェーズを無視して、フェーズを教師付け(annotation)に、状態を未作業(not started)に変更します。
タスクの担当者としては、直前の教師付け(annotation)フェーズの担当者を割り当てます。
この差戻しは差戻しとして扱われず、抜取検査・抜取受入のスキップ判定に影響を及ぼしません。

```
# tasks.txtに記載れたタスクを強制的に差し戻す
# 最後のannotation phaseを担当したユーザを割り当てます（画面と同じ動き）。検査コメントは付与しません。
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt 

# 受入完了の場合は、受入を取り消してから差し戻します
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt --cancel_acceptance

# 「hoge」という検査コメントを付与して、タスクを差し戻します。その際、担当者は割り当てません
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt \
 --comment "hoge" --not_assign

# 差し戻したタスクに、ユーザuser1を割り当てる
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt \
 --comment "hoge" --assigned_annotator_user_id user1


```



