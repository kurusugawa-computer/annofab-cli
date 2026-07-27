==========================================
comment create_inspection_simply
==========================================

Description
=================================
``comment create_inspection`` コマンドよりも、簡単に検査コメントを作成できます。

.. note::

    タスクが教師付けフェーズのときは、検査コメントを作成できません。検査コメントを作成するには、タスクのフェーズを「検査」または「受入」にする必要があります。


Examples
=================================

基本的な使い方
--------------------------

指定したタスクに、検査コメントを作成できます。
``--comment`` に検査コメントの内容を指定してください。
タスク内の先頭の入力データに、検査コメントが作成されます。

.. code-block::

    $ annofabcli comment create_inspection_simply --project_id prj1 --task_id task1 task2 \
     --comment "枠がズレています。"


``--phrase_id`` に定型指摘IDも指定できます。

.. code-block::

    $ annofabcli comment create_inspection_simply --project_id prj1 --task_id task1 task2 \
     --comment "枠がズレています。 #ID1" --phrase_id ID1


受入完了状態を取り消してから検査コメントを作成する
------------------------------------------------------

完了状態の受入フェーズに検査コメントを作成する場合は、 ``--cancel_acceptance`` を指定してください。
このオプションを指定すると、受入完了状態を取り消してから検査コメントを作成します。差し戻し前に検査コメントを作成する場合などに使用します。

.. code-block::

    $ annofabcli comment create_inspection_simply --project_id prj1 --task_id task1 \
    --comment "枠がズレています。" --cancel_acceptance


検査コメントの位置や区間を指定する
--------------------------------------

``--comment_data`` に、検査コメントの位置や区間をJSON形式で指定することができます。

以下は、 ``--comment_data`` に渡すJSON文字列のサンプルです。

.. code-block:: json
    :caption: 画像プロジェクト：(x=0,y=0)の位置に点

    {
        "x":0,
        "y":0,
        "_type": "Point"
    }


.. code-block:: json
    :caption: 動画プロジェクト：0〜100ミリ秒の区間

    {
        "start":0,
        "end":100,
        "_type": "Time"
    }


``--comment_data`` を指定しない場合は、以下の検査コメントが作成されます。

* 画像プロジェクト： 点。先頭画像の左上に位置する。
* 動画プロジェクト： 区間。動画の先頭に位置する。
* カスタムプロジェクト（3dpc）： 辺が1の立方体。先頭フレームの原点に位置する。

ただし、ビルトインのエディタプラグインを使用していないカスタムプロジェクトの場合は ``--custom_project_type`` が必須です。

.. code-block::

    $ annofabcli comment create_inspection_simply --project_id prj1 --task_id task1 \
    --comment "weather属性を見直してください。" \
    --custom_project_type 3dpc


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli comment create_inspection_simply --project_id prj1 --task_id t1 t2 t3 t4 \
    --parallelism 4 --yes


Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.create_inspection_comment_simply.add_parser
   :prog: annofabcli comment create_inspection_simply
   :nosubcommands:
   :nodefaultconst:
