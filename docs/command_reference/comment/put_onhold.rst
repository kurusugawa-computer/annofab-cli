==========================================
comment put_onhold
==========================================

Description
=================================
保留コメントを付与します。


.. note::

    2024年9月現在、保留コメントは画像エディタ画面でしか利用できません。動画エディタ画面、3次元エディタ画面では保留コメントを利用できません。
    
    


Examples
=================================

基本的な使い方
--------------------------

``--json`` に保留コメントの内容をJSON形式で指定すると、保留コメントを付与できます。

.. code-block:: json
    :caption: comment.json

    {
        "task1":{
            "input_data1": [
                {
                    "comment": "type属性が間違っています。",
                },
                {
                    "comment": "枠がズレています。",
                    "annotation_id": "foo",
                }
            ],
            "input_data2":[]
        },
        "task2": {
            "input_data3":[]
        }
    }


* 1階層目のキーはtask_id, 2階層目のキーはinput_data_idです。
* 保留コメントのプロパティとして指定できるキーは以下の通りです。

  * ``comment``：コメントの内容。必須。
  * ``annotation_id``：コメントに紐づくアノテーションのannotation_id
  * ``comment_id``：コメントID。省略した場合は自動的にUUIDv4が生成されます。


.. code-block::

    $ annofabcli comment put_onhold --project_id prj1 --json file://comment.json


CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、保留コメントを付与できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment,annotation_id,comment_id
    task001,input001,画像が間違っている,,
    task001,input002,確認が必要,anno789,


* CSVには以下の列が必要です。

  * ``task_id`` （必須）：タスクID
  * ``input_data_id`` （必須）：入力データID
  * ``comment`` （必須）：コメント本文
  * ``annotation_id`` （任意）：紐付けるアノテーションID
  * ``comment_id`` （任意）：コメントID（省略時はUUIDv4自動生成）


.. code-block::

    $ annofabcli comment put_onhold --project_id prj1 --csv comment.csv





並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli comment put_onhold --project_id prj1 --json file://comment.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.put_onhold_comment.add_parser
   :prog: annofabcli comment put_onhold
   :nosubcommands:
   :nodefaultconst:
