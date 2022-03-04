=================================
task complete
=================================

Description
=================================
教師付フェーズのタスクに対しては提出、検査または受入フェーズのタスクに対しては合格にして、次のフェーズに進めます。
ただし作業中また完了状態のタスクは、次のフェーズに進めません。


Examples
=================================


基本的な使い方
--------------------------------------

``--task_id`` に操作対象タスクのtask_idを指定してください。

.. code-block::
    :caption: task_id.txt

    task1
    task2
    ...

教師付フェーズのタスクに対して提出する
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

以下のコマンドは、教師付フェーズのタスクを提出して、次のフェーズに進めます。未回答の検査コメントがあるタスクはスキップします。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt --phase annotation

未回答の検査コメントがあるタスクも提出するには、``--reply_comment`` で未回答の検査コメントに対して返信する必要があります。
以下のコマンドは、未回答の検査コメントに「対応しました」と返信してからタスクを提出します。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt \
    --phase annotation --reply_comment "対応しました"



検査/受入フェーズのタスクに対して合格にする
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

以下のコマンドは、検査フェーズでフェーズステージ2のタスクを合格にして、次のフェーズに進めます。未処置の検査コメントがあるタスクはスキップします。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt \
    --phase inspection --phase_stage 2

未処置の検査コメントがあるタスクも合格にするには、``--inspection_status`` で未処置の検査コメントのステータスを変える必要があります。
検査コメントは以下のステータスに変更できます。

* ``resolved`` : 対応完了
* ``closed`` : 対応不要

以下のコマンドは、未処置の検査コメントは「対応不要」状態にしてから、受入フェーズのタスクを合格にします。

.. code-block::

    $ annofabcli  task complete --project_id prj1 --task_id file://task_id.txt \
    --phase acceptance --inspection_status closed



タスクのステータスや担当者で絞り込み
----------------------------------------------

``--task_query`` を指定すると、タスクのステータスや担当者で、操作対象のタスクを絞り込むことができます。


以下のコマンドは、``task_id.txt`` に記載されているタスクの内、ステータスが未着手のタスクに対して提出します。


.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt \
    --phase annotation --task_query '{"status":"not_started"}'




.. note::

    ``--task_query '{"phase":"annotation"}'`` のようにフェーズやフェーズステージを指定する必要はありません。
    ``annofabcli task complete`` コマンドは、``--phase`` , ``--phase_stage`` で、フェーズとフェーズステージを指定できるからです。



並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task_id.txt \
    --phase annotation --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.complete_tasks.add_parser
   :prog: annofabcli task complete
   :nosubcommands:
   :nodefaultconst: