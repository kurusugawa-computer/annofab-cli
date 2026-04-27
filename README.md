# annofab-cli
[Annofab](https://annofab.com/)のCLI(Command Line Interface)ツールです。
「タスクの一括差し戻し」や、「タスク一覧出力」など、Annofabの画面で実施するには時間がかかる操作を、コマンドとして提供しています。

[![PyPI version](https://badge.fury.io/py/annofabcli.svg)](https://badge.fury.io/py/annofabcli)
[![Python Versions](https://img.shields.io/pypi/pyversions/annofabcli.svg)](https://pypi.org/project/annofabcli/)
[![Documentation Status](https://readthedocs.org/projects/annofab-cli/badge/?version=latest)](https://annofab-cli.readthedocs.io/ja/latest/?badge=latest)


* [Annofab](https://annofab.com/)
* [annofab-cliのドキュメント](https://annofab-cli.readthedocs.io/ja/latest/)
* [開発用ドキュメント](https://github.com/kurusugawa-computer/annofab-cli/blob/main/README_for_developer.md)



# 注意
* 作者または著作権者は、ソフトウェアに関してなんら責任を負いません。
* 予告なく互換性のない変更がある可能性をご了承ください。
* Annofabプロジェクトに大きな変更を及ぼすコマンドも存在します。間違えて実行してしまわないよう、注意してご利用ください。


## 廃止予定
* TODO

# Requirements
* Python 3.10+

# Install

```
$ pip install annofabcli
```

https://pypi.org/project/annofabcli/

## Windows用の実行ファイルを利用する場合
[GitHubのリリースページ](https://github.com/kurusugawa-computer/annofab-cli/releases)から`annofabcli-vX.X.X-windows.zip`をダウンロードしてください。
zipの中にある`annofabcli.exe`が実行ファイルになります。



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

### 既存ラベルの `field_values` を更新する
アノテーション仕様に登録済みのラベルに対して、`field_values` を更新できます。
`field_values` には、サイズ制約、誤差許容、エディタ機能など、ラベルごとの設定をJSONオブジェクトで指定します。

まず現在の設定を確認したい場合は、`annotation_specs list_label` で `field_values` 列を出力します。

```bash
$ annofabcli annotation_specs list_label --project_id prj1 --output label.csv
```

既定動作はマージです。指定したキーだけを更新し、それ以外のキーは保持します。

```bash
$ annofabcli annotation_specs update_label_field_values --project_id prj1 \
  --label_name_en car bus \
  --field_values_json '{"margin_of_error_tolerance":{"_type":"MarginOfErrorTolerance","max_pixel":3}}'
```

`--replace` を指定すると、`field_values` 全体を指定したJSONオブジェクトで置換します。

```bash
$ annofabcli annotation_specs update_label_field_values --project_id prj1 \
  --label_name_en car \
  --field_values_json '{"display_line_direction":{"_type":"DisplayLineDirection","value":true}}' \
  --replace
```

`--clear` を指定すると、対象ラベルの `field_values` を空辞書に更新します。

```bash
$ annofabcli annotation_specs update_label_field_values --project_id prj1 \
  --label_name_en car \
  --clear
```

対象ラベルは `--label_name_en` の代わりに `--label_id` でも指定できます。
また、`--field_values_json` には `file://` を付けてJSONファイルを渡すこともできます。
