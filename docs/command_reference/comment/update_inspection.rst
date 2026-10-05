==========================================
comment update_inspection
==========================================

Description
=================================
検査コメントを更新します。

``comment_id`` が一致するコメントが存在する場合だけ更新します。存在しない場合はスキップします。

更新する項目だけを指定してください。省略した項目は既存値を保持します。
本文・座標・アノテーションとの紐付け・定型指摘のうち、変更する項目だけを指定できます。
コメントの状態や作成者、作成時のフェーズは保持します。

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
  * ``comment``：検査コメントの内容。省略時は既存値を保持します。空文字列で本文を空にできます。
  * ``data``：検査コメントの位置や区間。省略時は既存値を保持します。 ``null`` は指定できません。
  * ``annotation_id``：検査コメントに紐づくアノテーションのannotation_id。省略時は既存値を保持し、 ``null`` で紐付けを解除します。変更しても座標は自動補完されません。
  * ``phrases``：参照する定型指摘のIDの配列。省略時は既存値を保持し、空配列または ``null`` で解除します。

.. code-block::

    $ annofabcli comment update_inspection --project_id prj1 --json file://comment.json


座標だけを変更する場合
--------------------------

``comment`` を省略して ``data`` だけを指定できます。本文や定型指摘、アノテーションとの紐付けは保持します。

.. code-block:: json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment_id": "comment1",
            "data": {"x": 10, "y": 20, "_type": "Point"}
        }
    ]

CSV形式で指定する場合
--------------------------

``--csv`` にCSVファイルを指定すると、検査コメントを更新できます。

.. code-block:: text
    :caption: comment.csv

    task_id,input_data_id,comment_id,comment,data,annotation_id,phrases
    task001,input001,comment001,type属性が間違っています。,"{""x"":10,""y"":20,""_type"":""Point""}",,
    task001,input002,comment002,枠がズレています。,"{""x"":20,""y"":20,""_type"":""Point""}",anno123,"[""A1""]"

CSVの列は、JSONの各キーに対応しています。
``task_id``、``input_data_id``、``comment_id`` の列が必須です。
その他の列は省略でき、空欄も「変更なし」と扱います。
本文を空にする場合やアノテーションとの紐付けを解除する場合は、JSON形式を使用してください。

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
