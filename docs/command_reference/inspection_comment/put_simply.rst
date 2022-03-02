==========================================
inspection_comment put_simply
==========================================

Description
=================================
``inspection_comment put`` コマンドよりも、簡単に検査コメントを付与します。


Examples
=================================

基本的な使い方
--------------------------

指定したタスクに、検査コメントを付与できます。``--comment`` に検査コメントの内容を指定してください。 
タスク内の先頭の入力データに、検査コメントが付与されます。

.. code-block::

    $ annofabcli inspection_comment put_simply --project_id prj1 --task_id task1 task2 \
     --comment "枠がズレています。"


``--phrase_id`` に定型指摘IDも指定できます。


.. code-block::

    $ annofabcli inspection_comment put_simply --project_id prj1 --task_id task1 task2 \
     --comment "枠がズレています。 #ID1" --phrase_id ID1



検査コメントの位置や区間を指定する
--------------------------------------
``--comment_data`` に、検査コメントの位置や区間をJSON形式で指定することができます。
``--comment_data`` に渡す形式は、https://annofab.com/docs/api/#operation/batchUpdateInspections APIのリクエストボディ ``data`` を参照してください。


以下は、 ``--comment_data`` に渡すJSON文字列のサンプルです。

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


``--comment_data`` を指定しない場合は、以下の値になります。

* 画像プロジェクト： ``{"x":0, "y":0, "_type": "Point"}``
* 動画プロジェクト： ``{"start":0, "end":100, "_type": "Time"}``

カスタムプロジェクトの場合は、検査コメントの位置を決められないので、 ``--comment_data`` は必須です。












並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli inspection_comment put_simply --project_id prj1 --task_id t1 t2 t3 t4 \
    --parallelism 4 --yes


Usage Details
=================================

.. argparse::
   :ref: annofabcli.inspection_comment.put_inspection_comments_simply.add_parser
   :prog: annofabcli inspection_comment put
   :nosubcommands:
   :nodefaultconst:
