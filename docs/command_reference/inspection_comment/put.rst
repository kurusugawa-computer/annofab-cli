==========================================
inspection_comment put
==========================================

Description
=================================
検査コメントを付与します。



Examples
=================================

基本的な使い方
--------------------------

``--json`` に検査コメントの内容をJSON形式で指定してください。

.. code-block::
    :caption: comment.json

    {
        "task1":{
            "input_data1": [
                {
                    "comment": "type属性が間違っています。",
                    "data": { // 点で指摘
                        "x":10,
                        "y":20,
                        "_type": "Point"
                    }
                },
                {
                    "comment": "枠がズレています。 #A1",
                    "data": { // ポリラインで指摘
                        "coordinates":[
                            {"x":20, "y":20}, {"x":30, "y":30}
                        ],
                        "_type": "Polyline"
                    },
                    "annotation_id": "foo", //アノテーションに紐づける
                    "phrases": ["A1"] //定型指摘コメントを利用する
                }
            ],
            "input_data2":[{},{}, ...]
        },
        "task2": {
            "input_data3":[{},{}, ...]
        }
    }


* 1階層目のキーはtask_id, 2階層目のキーはinput_data_idです。
* 検査コメントのプロパティとして指定できるキーは以下の通りです。

  * ``comment``：検査コメントの内容。必須。
  * ``data``：検査コメントの位置や区間。必須。詳細は https://annofab.com/docs/api/#operation/batchUpdateInspections のリクエストボディを参照してください。
  * ``annotation_id``：検査コメントに紐づくアノテーションのannotation_id
  * ``phrases``：参照する定型指摘のIDの配列




.. code-block::

    $ annofabcli inspection_comment put --project_id prj1 --json file://comment.json
