==========================================
comment put_inspection
==========================================

Description
=================================
検査コメントを付与します。

.. note::

    タスクが教師付けフェーズのときは、検査コメントを付与できません。検査コメントを付与するには、タスクのフェーズを「検査」または「受入」にする必要があります。
    

Examples
=================================


comment_idを指定する場合
--------------------------

コメントIDを明示的に指定したい場合は、--comment_idオプションを利用します。

.. code-block::

    $ annofabcli comment put_inspection --project_id prj1 --json file://comment.json --comment_id my-comment-id-001



.. code-block:: json
    :caption: comment.json

    {
        "task1":{
            "input_data1": [
                {
                    "comment": "type属性が間違っています。",
                    "data": {
                        "x":10,
                        "y":20,
                        "_type": "Point"
                    }
                },
                {
                    "comment": "枠がズレています。 #A1",
                    "data": {
                        "coordinates":[
                            {"x":20, "y":20}, {"x":30, "y":30}
                        ],
                        "_type": "Polyline"
                    },
                    "annotation_id": "foo",
                    "phrases": ["A1"]
                }
            ]
        }
    }


* 1階層目のキーはtask_id, 2階層目のキーはinput_data_idです。
* 検査コメントのプロパティとして指定できるキーは以下の通りです。

  * ``comment``：検査コメントの内容。必須。
  * ``data``：検査コメントの位置や区間。必須。詳細は後述を参照してください。
  * ``annotation_id``：検査コメントに紐づくアノテーションのannotation_id
  * ``phrases``：参照する定型指摘のIDの配列

--comment_idオプションについて
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* ``--comment_id``で指定したIDが、付与されるコメントのIDとなります。
* 指定しない場合は自動生成されます。


.. code-block::

    $ annofabcli comment put_inspection --project_id prj1 --json file://comment.json


``data`` プロパティに渡す値の例
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


.. code-block:: json
    :caption: 画像プロジェクト：(x=0,y=0)の位置に点

    {
        "x":0,
        "y":0,
        "_type": "Point"
    }


.. code-block:: json
    :caption: 画像プロジェクト：(x=0,y=0),(x=100,y=100)のポリライン

    {
        "coordinates": [{"x":0, "y":0}, {"x":100, "y":100}],
        "_type": "Polyline"
    }


.. code-block:: json
    :caption: 動画プロジェクト：0〜100ミリ秒の区間

    {
        "start":0,
        "end":100,
        "_type": "Time"
    }


.. code-block:: json
    :caption: カスタムプロジェクト（3dpc editor）：原点付近に辺が1の立方体

    {
        "data": "{\"kind\": \"CUBOID\", \"shape\": {\"dimensions\": {\"width\": 1.0, \"height\": 1.0, \"depth\": 1.0}, \"location\": {\"x\": 0.0, \"y\": 0.0, \"z\": 0.0}, \"rotation\": {\"x\": 0.0, \"y\": 0.0, \"z\": 0.0}, \"direction\": {\"front\": {\"x\": 1.0, \"y\": 0.0, \"z\": 0.0}, \"up\": {\"x\": 0.0, \"y\": 0.0, \"z\": 1.0}}}, \"version\": \"2\"}",
        "_type": "Custom"    
    }





並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli comment put_inspection --project_id prj1 --json file://comment.json \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.put_inspection_comment.add_parser
   :prog: annofabcli comment put_inspection
   :nosubcommands:
   :nodefaultconst:
