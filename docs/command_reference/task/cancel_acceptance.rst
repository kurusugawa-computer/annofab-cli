=================================
task cancel_acceptance
=================================

Description
=================================
受け入れ完了タスクに対して、受け入れ取り消しを実施します。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に操作対象タスクのtask_idを指定してください。

受入取り消し後の担当者は、デフォルトでは最後に受入フェーズを担当したユーザになります。

.. code-block::
    :caption: task_id.txt

    task1
    task2
    ...


.. code-block::

    $ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task_id.txt


受入取り消し後の担当者を指定する場合は、``--assigned_acceptor_user_id`` に担当させたいユーザのuser_idを指定してください。


.. code-block::

    $ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task_id.txt \
     --assigned_acceptor_user_id user1


受入取り消し後の担当者を未割当にする場合は、``--not_assign`` を指定してください。

.. code-block::

    $ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task_id.txt \
    --not_assign


タスクのフェーズやステータスなどで絞り込み
----------------------------------------------

``--task_query`` を指定すると、タスクのフェーズやステータスなどで、操作対象のタスクを絞り込むことができます。


以下のコマンドは、``task_id.txt`` に記載されているタスクの内、担当者が未割当のタスクに対して受け入れ取り消しします。


.. code-block::

    $ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task_id.txt \
    --task_query '{"no_user":true}'


並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.cancel_acceptance.add_parser
   :prog: annofabcli task cancel_acceptance
   :nosubcommands:
   :nodefaultconst:
