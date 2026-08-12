==========================================
comment create_onhold_simply
==========================================

Description
=================================
``comment create_onhold`` コマンドよりも、簡単に保留コメントを作成できます。


Examples
=================================

基本的な使い方
--------------------------

指定したタスクに、保留コメントを作成できます。
``--comment`` に保留コメントの内容を指定してください。
タスク内の先頭の入力データに、保留コメントが作成されます。

.. code-block::

    $ annofabcli comment create_onhold_simply --project_id prj1 --task_id task1 task2 \
     --comment "枠がズレています。"

自身が担当者ではないタスクに保留コメントを作成する
------------------------------------------------------

:doc:`create_onhold` の「自身が担当者ではないタスクに保留コメントを作成する」を参照してください。


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli comment create_onhold_simply --project_id prj1 --task_id t1 t2 t3 t4 \
    --parallelism 4 --yes


Usage Details
=================================

.. argparse::
   :ref: annofabcli.comment.create_onhold_comment_simply.add_parser
   :prog: annofabcli comment create_onhold_simply
   :nosubcommands:
   :nodefaultconst:
