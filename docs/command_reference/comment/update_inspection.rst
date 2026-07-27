==========================================
comment update_inspection
==========================================

Description
=================================
検査コメントを更新します。

``comment_id`` が一致するコメントが存在する場合だけ更新します。存在しない場合はスキップします。

.. note::

    タスクが教師付けフェーズのときは、検査コメントを更新できません。検査コメントを更新するには、タスクのフェーズを「検査」または「受入」にする必要があります。

Examples
=================================

基本的な使い方
--------------------------

``--json`` に検査コメントの内容をJSON形式で指定すると、検査コメントを更新できます。

.. code-block:: json
    :caption: comment.json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment_id": "comment1",
            "comment": "type属性が間違っています。",
            "data": {
                "x": 10,
                "y": 20,
                "_type": "Point"
            }
        }
    ]

* JSONの各要素は1件の検査コメントを表します。
* 検査コメントのプロパティとして指定できるキーは以下の通りです。

  * ``task_id``：タスクID。必須。
  * ``input_data_id``：入力データID。必須。
  * ``comment_id``：コメントID。必須。
  * ``comment``：検査コメントの内容。必須。
  * ``data``：検査コメントの位置や区間。 ``annotation_id`` が指定されている場合はオプショナル。省略した場合は、アノテーション情報から自動補完されます。
  * ``annotation_id``：検査コメントに紐づくアノテーションのannotation_id。
  * ``phrases``：参照する定型指摘のIDの配列。

.. code-block::

    $ annofabcli comment update_inspection --project_id prj1 --json file://comment.json


CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、検査コメントを更新できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment_id,comment,data,annotation_id,phrases
    task001,input001,comment001,type属性が間違っています。,"{""x"":10,""y"":20,""_type"":""Point""}",,
    task001,input002,comment002,枠がズレています。,"{""x"":20,""y"":20,""_type"":""Point""}",anno123,"[""A1""]"

CSVの列は、JSONの各キーに対応しています。

並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli comment update_inspection --project_id prj1 --json file://comment.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.update_inspection_comment.add_parser
   :prog: annofabcli comment update_inspection
   :nosubcommands:
   :nodefaultconst:
