==========================================
comment update_onhold
==========================================

Description
=================================
保留コメントを更新します。

``comment_id`` が一致するコメントが存在する場合だけ更新します。存在しない場合はスキップします。

Examples
=================================

基本的な使い方
--------------------------

``--json`` に保留コメントの内容をJSON形式で指定すると、保留コメントを更新できます。

.. code-block:: json
    :caption: comment.json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment_id": "comment1",
            "comment": "画像が間違っています。"
        }
    ]

* JSONの各要素は1件の保留コメントを表します。
* 保留コメントのプロパティとして指定できるキーは以下の通りです。

  * ``task_id``：タスクID。必須。
  * ``input_data_id``：入力データID。必須。
  * ``comment_id``：コメントID。必須。
  * ``comment``：コメントの内容。必須。
  * ``annotation_id``：コメントに紐づくアノテーションのannotation_id。

.. code-block::

    $ annofabcli comment update_onhold --project_id prj1 --json file://comment.json


CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、保留コメントを更新できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment_id,comment,annotation_id
    task001,input001,comment001,画像が間違っている,
    task001,input002,comment002,確認が必要,anno789

CSVの列は、JSONの各キーに対応しています。

並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli comment update_onhold --project_id prj1 --json file://comment.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.update_onhold_comment.add_parser
   :prog: annofabcli comment update_onhold
   :nosubcommands:
   :nodefaultconst:
