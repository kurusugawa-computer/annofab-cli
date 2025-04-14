==========================================
comment put_onhold_simply
==========================================

Description
=================================
``comment put_onhold`` コマンドよりも、簡単に保留コメントを付与できます。

.. note::

    2024年9月現在、保留コメントは画像エディタ画面でしか利用できません。動画エディタ画面、3次元エディタ画面では保留コメントを利用できません。
    


Examples
=================================

基本的な使い方
--------------------------

指定したタスクに、保留コメントを付与できます。
``--comment`` にコメントの内容を指定してください。 
タスク内の先頭の入力データに、保留コメントが付与されます。

.. code-block::

    $ annofabcli comment put_onhold_simply --project_id prj1 --task_id task1 task2 \
     --comment "枠がズレています。"



並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli comment put_onhold_simply --project_id prj1 --task_id t1 t2 t3 t4 \
    --parallelism 4 --yes


Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.put_onhold_comment_simply.add_parser
   :prog: annofabcli comment put_onhold_simply
   :nosubcommands:
   :nodefaultconst:
