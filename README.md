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


### filesystem filter_annotation
アノテーションzipから特定のファイルを絞り込んで、zip展開します。


```
# アノテーションzipからcomplete状態で、task.txtに記載されているtask_idを除外した状態で、展開する
$ annofabcli filesystem filter_annotation --annotation annotation.zip \
 --task_query '{"status":"complete"}'  --exclude_task_id file://task.txt --output_dir

```


### filesystem
https://annofab-cli.readthedocs.io/ja/latest/command_reference/filesystem/index.html 参照

### input_data 
https://annofab-cli.readthedocs.io/ja/latest/command_reference/input_data/index.html 参照



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



### inspection_comment list_with_json
検査コメント一覧を出力します。

```
# 検査コメント全件を出力する
$ annofabcli inspection_comment list_with_json --project_id prj1 --output inspection_comment.csv

```



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


### instruction
https://annofab-cli.readthedocs.io/ja/latest/command_reference/instruction/index.html 参照


### job
https://annofab-cli.readthedocs.io/ja/latest/command_reference/job/index.html 参照





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




### project
https://annofab-cli.readthedocs.io/ja/latest/command_reference/project/index.html 参照

### project_member
https://annofab-cli.readthedocs.io/ja/latest/command_reference/project_member/index.html 参照

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

### statistics merge_visualization_dir
`annofabcli statistics visualize`コマンドの出力結果をマージします。


```
$ annofabcli statistics visualize --project_id prj1 --output outdir1
$ annofabcli statistics visualize --project_id prj2 --output outdir2
$ annofabcli statistics merge_visualization_dir --dir outdir1 outdir2 --output_dir merge_dir
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

# prj, prj2 の統計情報を、/tmp/outputにプロジェクトごとに出力します。
$ annofabcli statistics visualize --project_id prj1 prj2 --output_dir /tmp/output

# prj, prj2, prj3, prj4 の統計情報を、並列処理で出力します。
$ annofabcli statistics visualize --project_id prj1 prj2 prj3 prj4  --output_dir /tmp/output --parallelism 2

# prj, prj2 の統計情報を、/tmp/outputにプロジェクトごとに出力し、prj1,prj2の統計情報をマージした情報も、`merge`ディレクトリに出力します。
$ annofabcli statistics visualize --project_id prj1 prj2 --output_dir /tmp/output --merge

```


### supplementary
https://annofab-cli.readthedocs.io/ja/latest/command_reference/supplementary/index.html 参照


### task
https://annofab-cli.readthedocs.io/ja/latest/command_reference/task/index.html 参照

### task_history
https://annofab-cli.readthedocs.io/ja/latest/command_reference/task_history/index.html 参照
