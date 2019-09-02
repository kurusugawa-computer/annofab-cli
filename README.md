# 概要
annofabapiを使ったCLI(Command Line Interface)ツールです。
「タスクの一括差し戻し」や、「プロジェクト間の差分表示」など、AnnoFabの画面で実施するには時間がかかる操作を、コマンドとして提供しています。

# 注意
* 作者または著作権者は、ソフトウェアに関してなんら責任を負いません。
* 予告なく互換性のない変更がある可能性をご了承ください。
* AnnoFabプロジェクトに大きな変更を及ぼすコマンドも存在します。間違えて実行してしまわないよう、注意してご利用ください。


## 廃止予定
なし

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

AnnoFabの認証情報は、以下の順に読み込まれます。
1. `.netrc`ファイル
2. 環境変数

## Dockerを利用する場合

```
$ git clone https://github.com/kurusugawa-computer/annofab-cli.git
$ cd annofab-cli
$ chmod u+x docker-build.sh
$ ./docker-build.sh

$ docker run -it annofab-cli annofabcli --help

# AnnoFabの認証情報を標準入力から指定する
$ docker run -it annofab-cli annofabcli diff_projects prj1 prj2
Enter AnnoFab User ID: XXXXXX
Enter AnnoFab Password: 

# AnnoFabの認証情報を環境変数で指定する
$ docker run -it -e ANNOFAB_USER_ID=XXXX -e ANNOFAB_PASSWORD=YYYYY annofab-cli annofabcli project diff prj1 prj2
```

# 機能一覧

|コマンド| サブコマンド                  | 内容                                                                                                     |必要なロール|
|----|-------------------------------|----------------------------------------------------------------------------------------------------------|------------|
|annotation| list_count | task_idまたはinput_data_idで集約したアノテーションの個数を出力します                              |-|
|annotation_specs| list_label | アノテーション仕様のラベル情報を出力する                              |チェッカー/オーナ|
|annotation_specs| list_label_color             | アノテーション仕様から、label_nameとRGBを対応付けたJSONを出力する。                                      |チェッカー/オーナ|
|input_data|list             | 入力データ一覧を出力する。                                                            |-|
|inspection_comment| list | 検査コメントを出力する。                               |-|
|inspection_comment| list_unprocessed | 未処置の検査コメントを出力する。                               |-|
|instruction| upload             | HTMLファイルを作業ガイドとして登録する。                                                           |チェッカー/オーナ|
|project| diff                 | プロジェクト間の差分を表示する                                                                           |チェッカー/オーナ|
|project| download                 | タスクや検査コメント、アノテーションなどをダウンロードします。                                                                           |オーナ|
|project_member| list                  | プロジェクトメンバ一覧を出力する                                                                |-|
|project_member| invite                  | 複数のプロジェクトに、ユーザを招待する。                                                                 |オーナ|
|project_member| delete                  | 複数のプロジェクトからユーザを削除する。                                                                 |オーナ|
|project_member| copy                  | プロジェクトメンバをコピーする。|オーナ(コピー先プロジェクトに対して)|
|project_member| put                  | プロジェクトメンバに、CSVに記載されたユーザを登録する。|オーナ|
|statistics| visualize             | 統計情報を可視化する。                                                            |オーナ|
|task| cancel_acceptance             | 受け入れ完了タスクを、受け入れ取り消しする。                                                             |オーナ|
|task| change_operator             | タスクの担当者を変更する。                                                             |チェッカー/オーナ|
|task| complete                | 未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にする。                                 |チェッカー/オーナ|
|task|list             | タスク一覧を出力する。                                                            |-|
|task| reject                  | 検査コメントを付与してタスクを差し戻す。                                                                 |チェッカー/オーナ|
|filesystem| write_annotation_image        | アノテーションzip、またはそれを展開したディレクトリから、アノテーションの画像（Semantic Segmentation用）を生成する。 |-|


# Usage


## 共通のオプション引数


### `--csv_format`
CSVのフォーマットをJSON形式で指定します。`--format`が`csv`でないときは、このオプションは無視されます。
先頭に`file://`を付けると、JSON形式のファイルを指定できます。
指定した値は、[pandas.DataFrame.to_csv](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.to_csv.html) の引数として渡されます。
デフォルトはカンマ区切り、BOM付きUTF-8で出力されます。

```
--csv_format '{"sep": "\t"}'
```


### `--disable_log`
ログを無効化にします。

### `f` / `--format`
出力フォーマットを指定します。基本的に以下のフォーマットを指定できます。
* `csv` : CSV(デフォルとはカンマ区切り)
* `json` : インデントや空白がないJSON
* `pretty_json` : インデントされたJSON

list系のコマンドで利用できます。

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


### `-o` / `--output`
出力先のファイルパスを指定します。指定しない場合は、標準出力に出力されます。
list系のコマンドで利用できます。


### `-p` / `--project_id`
対象のプロジェクトのproject_idを指定します。

### `-q` / `--query`
JMESPathを指定します。出力結果の抽出や、出力内容の変更に利用できます。
http://jmespath.org/


### `-t` / `--task_id`
対象のタスクのtask_idを指定します。`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。

* 相対パスで指定： `--task_id file://task.txt`
* 絶対パスで指定： `--task_id file:///tmp/task.txt`

### `--yes`
処理中に現れる問い合わせに対して、常に'yes'と回答します。


## デフォルトのログ設定
* 標準エラー出力とログファイルに出力されます。
* カレントディレクトリの`.log`ディレクトリに、`annofabcli.log`というログファイルが生成されます。
* 1日ごとにログロテートされます

詳細は https://github.com/kurusugawa-computer/annofab-cli/blob/master/annofabcli/data/logging.yaml を参照してください。


## よくある使い方

### 受入完了のタスクを差し戻す
"car"ラベルの"occluded"属性のアノテーションルールに間違いがあったため、以下の条件を満たすタスクを一括で差し戻します。
* "car"ラベルの"occluded"チェックボックスがONのアノテーションが、タスクに1つ以上存在する。

前提条件
* プロジェクトのオーナが、annofabcliコマンドを実行する


```
# 受入完了のタスクのtask_id一覧を、acceptance_complete_task_id.txtに出力する。
$ annofabcli task list --project_id prj1  --task_query '{"phase": "complete","phase":"acceptance"}' --format task_id_list --output acceptance_complete_task_id.txt

# 受入完了タスクの中で、 "car"ラベルの"occluded"チェックボックスがONのアノテーションの個数を出力する。
$ annofabcli annotation list_count --project_id prj1 --task_id file://task.txt --output annotation_count.csv \
 --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}'

# annotation_count.csvを表計算ソフトで開き、アノテーションの個数が1個以上のタスクのtask_id一覧を、task_id.txtに保存する。

# task_id.txtに記載されたタスクに対して、受入完了状態を取り消す。
$ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task_id.txt

# task_id.txtに記載されたタスクを差し戻す。検査コメントは「carラベルのoccluded属性を見直してください」。差し戻したタスクには、最後のannotation phaseを担当したユーザを割り当てる（画面と同じ動き）。
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt --comment "carラベルのoccluded属性を見直してください"

```

### プロジェクトメンバをCSVで管理する

```
# prj1のプロジェクトメンバをCSVで出力する
$ annofabcli project_member list -p prj1 -f csv -o members.csv \
 --csv_format '{"columns": ["user_id","member_role"],"header":false}' 


# members.csvの中身を確認
$ head members.csv
user1,worker
user2,accepter
...


# members.csvに記載れたメンバを prj2に登録する
$ annofabcli project_member put -p prj2 --csv members.csv

```


## コマンド一覧




### annotation list_count
task_idまたはinput_data_idで集約したアノテーションの個数をCSV形式で出力します。
クエリのフォーマットは、[getAnnotationList API](https://annofab.com/docs/api/#operation/getAnnotationList)のクエリパラメータの`query`キー配下と同じです。
`label_name_en`(label_idに対応), `additional_data_definition_name_en`(additional_data_definition_idに対応) キーも指定できます。


```
# car ラベルのアノテーション個数を出力する(task_idで集約)
$ annofabcli annotation list_count -p prj1 --annotation_query '{"label_name_en": "car"}'

# car ラベルのアノテーション個数を出力する(input_data_idで集約)
$ annofabcli annotation list_count -p prj1 --annotation_query '{"label_name_en": "car"}' --gropu_by input_data_id

# task.txtに記載されたtask_idの一覧から、car ラベルのアノテーション個数を出力する
$ annofabcli annotation list_count -p prj1 --annotation_query '{"label_name_en": "car"}'  --task_id file://task.txt

# carラベルの"occluded"チェックボックスがONのアノテーションの個数を出力する
$ annofabcli annotation list_count -p prj1 --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}'

```



### annotation_specs list_label
アノテーション仕様のラベル情報を出力します。

```
# prj1のアノテーション仕様のラベル情報を、人間が見やすい形式で出力する
$ annofabcli annotation_specs list_label --project_id prj1

# prj1のアノテーション仕様のラベル情報を、インデントされたJSONで出力する。
$ annofabcli annotation_specs list_label --project_id prj1 --format pretty_json

```



### annotation_specs list_label_color
アノテーション仕様から、label_name(english)とRGBを対応付けたJSONを出力します。

```
$ annofabcli annotation_specs list_label_color --project_id prj1 
```

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




### input_data list
入力データ一覧を出力します。

```
# input_data_nameが"sample"の入力データ一覧を出力する
$ annofabcli input_data list --project_id prj1 --input_data_query '{"input_data_name": "sample"}' 

# 入力データの詳細情報も出力する
$ annofabcli input_data list --project_id prj1 --input_data_query '{"input_data_name": "sample"}' --add_details

```



### inspection_comment list
検査コメント一覧を出力します。

```
# task1, task2の検査コメント一覧を、CSVで出力する
$ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2

# タブ区切りの"out.tsv"を出力する
$ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2 --format csv --csv_format '{"sep":"\t"}'  --output out.tsv

# JSONで出力する
$ annofabcli inspection_comment list --project_id prj1 --task_id file://task.txt --format json
 
```


### inspection_comment list_unprocessed
未処置の検査コメント一覧を出力します。

```
# 未処置の検査コメント一覧を出力する
$ annofabcli inspection_comment list_unprocessed --project_id prj1 --task_id file://task.txt

# 未処置で、user1が"hoge"とコメントした検査コメント一覧を出力する
$ annofabcli inspection_comment list_unprocessed  --project_id prj1 --task_id file://task.txt --inspection_comment "hoge" --commenter_user_id user1 --format pretty_json --output inspection.json
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







### project diff
プロジェクト間の差分を表示します。差分がない場合、標準出力は空になります。
同じアノテーションルールのプロジェクトが複数ある場合、各種情報が同一であることを確認するときに、利用します。


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
タスクや検査コメント、アノテーションなどをダウンロードします。


```
# タスクの全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project download task --project_id prj1 --output task.json

# 検査コメントの全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project  download inspection_comment --project_id prj1 --output inspection_comment.json

# タスク履歴イベントの全一覧が記載されたJSONファイルをダウンロードする
$ annofabcli project download task_history_event --project_id prj1 --output task_history_event.json

# Simpleアノテーションのzipファイルをダウンロードする
$ annofabcli project download simple_annotation --project_id prj1 --output simple_annotation.zip

# 最新のFullアノテーションのzipファイルをダウンロードする（数分待つ）
$ annofabcli project download full_annotation --project_id prj1 --output full_annotation.zip --latest
DEBUG    : 2019-07-16 12:15:14,647 : annofabcli.common.facade       : job_id = c566c842-d84c-43d8-9f61-42fe5960c0fb のジョブが進行中です。60秒間待ちます。
DEBUG    : 2019-07-16 12:16:15,053 : annofabcli.common.facade       : job_id = c566c842-d84c-43d8-9f61-42fe5960c0fb のジョブが進行中です。60秒間待ちます。
DEBUG    : 2019-07-16 12:17:15,457 : annofabcli.common.facade       : job_id = c566c842-d84c-43d8-9f61-42fe5960c0fb のジョブが進行中です。60秒間待ちます。
DEBUG    : 2019-07-16 12:18:15,710 : annofabcli.common.facade       : job_id = c566c842-d84c-43d8-9f61-42fe5960c0fb のジョブが成功しました。ダウンロードを開始します。

```


### project_member list
プロジェクトメンバ一覧を出力する。

```
# ORG組織配下のすべてのプロジェクトのプロジェクトメンバ一覧を出力する
$ annofabcli project_member list --organization ORG

# prj1, prj2のプロジェクトのプロジェクトメンバ一覧を出力する
$ annofabcli project_member list --project_id prj1 prj2
```


### project_member invite
複数のプロジェクトに、ユーザを招待します。

```
# ORG組織配下のすべてのプロジェクトに、user1, user2をownerロールで招待する
$ annofabcli project_member invite --user_id user1 user2 --role owner --organization ORG

# prj1, prj2のプロジェクトに、user1をaccepterロールで招待する
$ annofabcli project_member invite --user_id user1 --role accepter --project_id prj1 prj2
```


### project_member delete
複数のプロジェクトからユーザを削除します。

```
# ORG組織配下のすべてのプロジェクトから、user1, user2を削除する
$ annofabcli project_member delete --user_id user1 user2  --organization ORG

# prj1, prj2のプロジェクトからuser1をaccepterロールで招待する
$ annofabcli project_member invite --user_id user1  --project_id prj1 prj2
```


### project_member copy
プロジェクトメンバをコピーします。

```
# prj1のメンバをprj2にコピーする。
$ annofabcli project_member copy prj1 prj2

# prj1のメンバをprj2にコピーする。prj2にしか存在しないメンバは削除される。
$ annofabcli project_member copy prj1 prj2 --delete_dest
```

### project_member put
CSVに記載されたユーザを、プロジェクトメンバとして登録します。

members.csvの中身は以下の通り。

```
user1, worker
user2, accepter
```


```
# CSVに記載れたユーザを、prj1プロジェクトのメンバとして登録します。
$ annofabcli project_member put --project_id prj1 --csv members.csv

# CSVに記載れたユーザを、prj1プロジェクトのメンバとして登録します。csvに記載されていないユーザは削除します。
$ annofabcli project_member put --project_id prj1 --csv members.csv --delete
```

### staistics visualize
統計情報を可視化します。

```
# prj1の統計情報を可視化したファイルを、/tmp/outputに出力する
$ annofabcli staistics visualize --project_id prj1 --output_dir /tmp/output

# statusがcompleteのタスクを統計情報を可視化したファイルを、/tmp/outputに出力する
$ annofabcli staistics visualize --project_id prj1 --output_dir /tmp/output \
  --task_query '{"status": "complete"}' 

# 作業ディレクトリ（`.annofab-cli`）内のファイルから、統計情報を可視化する。
$ annofabcli staistics visualize --project_id prj1 --not_update
```



### task list
タスク一覧を出力します。

```
# 受入フェーズで、"usr1"が担当しているタスクの一覧を出力する
$ annofabcli task list --project_id prj1 --task_query '{"user_id": "usr1","phase":"acceptance"}' 

# 休憩中で、過去の担当者が"usr1"であるタスクの一覧を出力する。task.jsonファイルにJSON形式で出力する。
$ annofabcli task list --project_id prj1 --task_query '{"previous_user_id": "usr1","status":"break"}' --format json --out task.json

# 差し戻されたタスクのtask_idを出力する
$ annofabcli task list --project_id prj1 --task_query '{"rejected_only": true}' --format task_id_list

 
```

### task cancel_acceptance
受け入れ完了タスクを、受け入れ取り消しにします。
アノテーションルールを途中で変更したときなどに、利用します。


```
# prj1プロジェクトのタスクを、受け入れ取り消しにする。再度受け入れを担当させるユーザは未担当
$ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt

# prj1プロジェクトのタスクを、受け入れ取り消しにする。再度受け入れを担当させるユーザはuser1
$ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt --user_id user1
```


### task change_operator
タスクの担当者を変更します。


```
# 指定されたタスクの担当者を 'user1' に変更する。
$ annofabcli task change_operator --project_id prj1 --task_id file://task.txt --user_id usr1

# 指定されたタスクの担当者を未割り当てに変更する。
$ annofabcli task change_operator --project_id prj1 --task_id file://task.txt --not_assign
```


### task complete
未処置の検査コメントを適切な状態に変更して、タスクを受け入れ完了にします。
特定のタスクのみ受け入れをスキップしたいときに、利用します。

```
# 未処置の検査コメントは"対応完了"状態にして、prj1プロジェクトのタスクを受け入れ完了にする。
$ annofabcli complete_tasks --project_id prj1  --inspection_list inspection.json --inspection_status error_corrected

# 未処置の検査コメントは"対応不要"状態にして、prj1プロジェクトのタスクを受け入れ完了にする。
$ annofabcli complete_tasks --project_id prj1  --inspection_list inspection.json --inspection_status no_correction_required
```

inspection.jsonは、未処置の検査コメント一覧です。`inspection_comment list_unprocessed`コマンドで出力できます。



### task reject
検査コメントを付与して、タスクを差し戻します。検査コメントは、タスク内の先頭の画像の左上に付与します。
アノテーションルールを途中で変更したときなどに、利用します。


```
# prj1プロジェクトに、"hoge"という検査コメントを付与して、タスクを差し戻す。最後のannotation phaseを担当したユーザを割り当てる（画面と同じ動き）
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt --comment "hoge"

# 差し戻したタスクに、担当者は割り当てない
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt --comment "hoge" --not_assign

# 差し戻したタスクに、ユーザuser1を割り当てる
$ annofabcli task reject --project_id prj1 --task_id file://tasks.txt --comment "hoge" --assigned_annotator_user_id user1
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

