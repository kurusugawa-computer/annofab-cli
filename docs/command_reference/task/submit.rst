============
task submit
============

Description
=================================
教師付フェーズのタスクを提出して、次のフェーズに進めます。
未回答の検査コメントがあるタスクを提出するには、``--reply_comment`` を指定してください。
作業中または完了状態のタスクは、次のフェーズに進めません。

Examples
=================================

以下のコマンドは、教師付フェーズのタスクを提出します。未回答の検査コメントがあるタスクはスキップします。

.. code-block::

    $ annofabcli task submit --project_id prj1 --task_id file://task_id.txt

未回答の検査コメントがあるタスクも提出するには、返信コメントを指定します。

.. code-block::

    $ annofabcli task submit --project_id prj1 --task_id file://task_id.txt \
    --reply_comment "対応しました"

タスクのステータスや担当者で絞り込むには、``--task_query`` を指定します。

.. code-block::

    $ annofabcli task submit --project_id prj1 --task_id file://task_id.txt \
    --task_query '{"status":"not_started"}'

並列数4で実行するには、``--parallelism`` と ``--yes`` を指定します。

.. code-block::

    $ annofabcli task submit --project_id prj1 --task_id file://task_id.txt \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.complete_tasks.add_submit_parser
   :prog: annofabcli task submit
   :nosubcommands:
   :nodefaultconst:
