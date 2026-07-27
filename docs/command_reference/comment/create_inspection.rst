==========================================
comment create_inspection
==========================================

Description
=================================
検査コメントを作成します。

``comment_id`` が一致するコメントが既に存在する場合は、デフォルトではスキップします。コメントを上書きする場合は、 ``--overwrite`` を指定してください。

.. note::

    タスクが教師付けフェーズのときは、検査コメントを作成できません。検査コメントを作成するには、タスクのフェーズを「検査」または「受入」にする必要があります。

Examples
=================================

基本的な使い方
--------------------------

``--json`` に検査コメントの内容をJSON形式で指定すると、検査コメントを作成できます。

.. code-block:: json
    :caption: comment.json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment": "type属性が間違っています。",
            "data": {
                "x": 10,
                "y": 20,
                "_type": "Point"
            }
        },
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment": "枠がズレています。 #A1",
            "data": {
                "coordinates": [
                    {"x": 20, "y": 20},
                    {"x": 30, "y": 30}
                ],
                "_type": "Polyline"
            },
            "annotation_id": "foo",
            "phrases": ["A1"],
            "comment_id": "comment1"
        }
    ]

* JSONの各要素は1件の検査コメントを表します。
* 検査コメントのプロパティとして指定できるキーは以下の通りです。

  * ``task_id``：タスクID。必須。
  * ``input_data_id``：入力データID。必須。
  * ``comment``：検査コメントの内容。必須。
  * ``data``：検査コメントの位置や区間。 ``annotation_id`` が指定されていない場合は必須。 ``annotation_id`` が指定されている場合はオプショナル。省略した場合は、アノテーション情報から自動補完されます。
  * ``annotation_id``：検査コメントに紐づくアノテーションのannotation_id。
  * ``phrases``：参照する定型指摘のIDの配列。
  * ``comment_id``：コメントID。省略した場合は自動的にUUIDv4が生成されます。

.. code-block::

    $ annofabcli comment create_inspection --project_id prj1 --json file://comment.json


CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、検査コメントを作成できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment,data,annotation_id,phrases,comment_id
    task001,input001,type属性が間違っています。,"{""x"":10,""y"":20,""_type"":""Point""}",,,
    task001,input002,枠がズレています。,"{""x"":20,""y"":20,""_type"":""Point""}",anno123,"[""A1""]",

CSVの列は、JSONの各キーに対応しています。

既存コメントを上書きする
--------------------------

``comment_id`` が一致するコメントを上書きする場合は、 ``--overwrite`` を指定してください。

.. code-block::

    $ annofabcli comment create_inspection --project_id prj1 --json file://comment.json --overwrite


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli comment create_inspection --project_id prj1 --json file://comment.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.create_inspection_comment.add_parser
   :prog: annofabcli comment create_inspection
   :nosubcommands:
   :nodefaultconst:
