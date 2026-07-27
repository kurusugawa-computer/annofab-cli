==========================================
comment create_onhold
==========================================

Description
=================================
保留コメントを作成します。

``comment_id`` が一致するコメントが既に存在する場合は、デフォルトではスキップします。コメントを上書きする場合は、 ``--overwrite`` を指定してください。

Examples
=================================

基本的な使い方
--------------------------

``--json`` に保留コメントの内容をJSON形式で指定すると、保留コメントを作成できます。

.. code-block:: json
    :caption: comment.json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment": "画像が間違っています。"
        },
        {
            "task_id": "task1",
            "input_data_id": "input_data2",
            "comment": "確認が必要です。",
            "annotation_id": "foo",
            "comment_id": "comment1"
        }
    ]

* JSONの各要素は1件の保留コメントを表します。
* 保留コメントのプロパティとして指定できるキーは以下の通りです。

  * ``task_id``：タスクID。必須。
  * ``input_data_id``：入力データID。必須。
  * ``comment``：コメントの内容。必須。
  * ``annotation_id``：コメントに紐づくアノテーションのannotation_id。
  * ``comment_id``：コメントID。省略した場合は自動的にUUIDv4が生成されます。

.. code-block::

    $ annofabcli comment create_onhold --project_id prj1 --json file://comment.json


CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、保留コメントを作成できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment,annotation_id,comment_id
    task001,input001,画像が間違っている,,
    task001,input002,確認が必要,anno789,

CSVの列は、JSONの各キーに対応しています。

既存コメントを上書きする
--------------------------

``comment_id`` が一致するコメントを上書きする場合は、 ``--overwrite`` を指定してください。

.. code-block::

    $ annofabcli comment create_onhold --project_id prj1 --json file://comment.json --overwrite


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli comment create_onhold --project_id prj1 --json file://comment.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.create_onhold_comment.add_parser
   :prog: annofabcli comment create_onhold
   :nosubcommands:
   :nodefaultconst:
