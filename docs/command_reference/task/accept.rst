============
task accept
============

Description
=================================
検査または受入フェーズのタスクを合格にして、次のフェーズに進めます。
未処置の検査コメントがあるタスクを合格にするには、``--inspection_status`` を指定してください。
作業中また完了状態のタスクは、次のフェーズに進めません。

Examples
=================================

以下のコマンドは、検査フェーズでフェーズステージ2のタスクを合格にします。未処置の検査コメントがあるタスクはスキップします。

.. code-block::

    $ annofabcli task accept --project_id prj1 --task_id file://task_id.txt \
    --phase inspection --phase_stage 2

以下のコマンドは、受入フェーズのタスクを合格にし、未処置の検査コメントを「対応不要」にします。

.. code-block::

    $ annofabcli task accept --project_id prj1 --task_id file://task_id.txt \
    --phase acceptance --inspection_status closed

タスクのステータスや担当者で絞り込むには、``--task_query`` を指定します。

.. code-block::

    $ annofabcli task accept --project_id prj1 --task_id file://task_id.txt \
    --phase inspection --task_query '{"status":"not_started"}'

並列数4で実行するには、``--parallelism`` と ``--yes`` を指定します。

.. code-block::

    $ annofabcli task accept --project_id prj1 --task_id file://task_id.txt \
    --phase acceptance --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.complete_tasks.add_accept_parser
   :prog: annofabcli task accept
   :nosubcommands:
   :nodefaultconst:
