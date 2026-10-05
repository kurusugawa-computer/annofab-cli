==========================================
comment update_onhold
==========================================

Description
=================================
保留コメントを更新します。

``comment_id`` が一致するコメントが存在する場合だけ更新します。存在しない場合はスキップします。

更新する項目だけを指定してください。省略した項目は既存値を保持します。
本文やアノテーションとの紐付けを更新しても、コメントの状態は保持します。

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
  * ``comment``：コメントの内容。省略時は既存値を保持します。空文字列で本文を空にできます。
  * ``annotation_id``：コメントに紐づくアノテーションのannotation_id。省略時は既存値を保持し、 ``null`` で紐付けを解除します。

.. code-block::

    $ annofabcli comment update_onhold --project_id prj1 --json file://comment.json


アノテーションとの紐付けだけを変更する場合
----------------------------------------------

``comment`` を省略して ``annotation_id`` だけを指定できます。本文は保持します。

.. code-block:: json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment_id": "comment1",
            "annotation_id": "anno789"
        }
    ]

CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、保留コメントを更新できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment_id,comment,annotation_id
    task001,input001,comment001,画像が間違っている,
    task001,input002,comment002,確認が必要,anno789

CSVの列は、JSONの各キーに対応しています。
``task_id``、``input_data_id``、``comment_id`` の列が必須です。
その他の列は省略でき、空欄も「変更なし」と扱います。
本文を空にする場合やアノテーションとの紐付けを解除する場合は、JSON形式を使用してください。

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
