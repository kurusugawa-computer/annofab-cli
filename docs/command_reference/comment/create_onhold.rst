==========================================
comment create_onhold
==========================================

Description
=================================
保留コメントを作成します。

``comment_id`` が一致するコメントが既に存在する場合はスキップします。既存コメントを変更する場合は、 :doc:`update_onhold` コマンドを使用してください。

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

自身が担当者ではないタスクに保留コメントを作成する
------------------------------------------------------

オーナーまたはチェッカーロールで、自身が担当者ではないタスクに保留コメントを作成する場合は、 ``--change_operator_to_me`` を指定してください。タスクの担当者を一時的に自分自身へ変更して保留コメントを作成し、処理後に元の担当者へ戻します。ワーカーロールは、自身が担当するタスクだけに保留コメントを作成できます。

.. code-block::

    $ annofabcli comment create_onhold --project_id prj1 --json file://comment.json \
    --change_operator_to_me

休憩中状態・保留中状態のタスクに保留コメントを作成する
----------------------------------------------------------

デフォルトでは、休憩中状態と保留中状態のタスクはスキップします。休憩中状態のタスクも処理する場合は ``--include_break_task`` 、保留中状態のタスクも処理する場合は ``--include_on_hold_task`` を指定してください。

保留中状態のタスクを処理した場合、保留コメントの作成後は休憩中状態になります。

.. code-block::

    $ annofabcli comment create_onhold --project_id prj1 --json file://comment.json \
    --include_break_task --include_on_hold_task

CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、保留コメントを作成できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment,annotation_id,comment_id
    task001,input001,画像が間違っている,,
    task001,input002,確認が必要,anno789,

CSVの列は、JSONの各キーに対応しています。

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
