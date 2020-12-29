=================================
task complete
=================================

Description
=================================
教師付フェーズのタスクに対しては提出、検査または受入フェーズのタスクに対しては合格にして、次のフェーズに進めます。



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

    $ annofabcli task complete --project_id prj1 --task_id file://task.txt --phase annotation

未回答の検査コメントがあるタスクも提出するには、``--reply_comment`` で未回答の検査コメントに対して返信する必要があります。
以下のコマンドは、未回答の検査コメントに「対応しました」と返信してからタスクを提出します。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task.txt \
    --phase annotation --reply_comment "対応しました"



検査/受入フェーズのタスクに対して合格にする
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

以下のコマンドは、検査フェーズでフェーズステージ2のタスクを合格にして、次のフェーズに進めます。未処置の検査コメントがあるタスクはスキップします。

.. code-block::

    $ annofabcli task complete --project_id prj1 --task_id file://task.txt \
    --phase inspection --phase_stage 2

未処置の検査コメントがあるタスクも合格にするには、``--inspection_status`` で未処置の検査コメントのステータスを変える必要があります。
検査コメントは以下のステータスに変更できます。

* ``error_corrected`` : 対応完了
* ``no_correction_required`` : 対応不要

以下のコマンドは、未処置の検査コメントは「対応不要」状態にしてから、受入フェーズのタスクを合格にします。

.. code-block::

    $ annofabcli  task complete --project_id prj1 --task_id file://task.txt \
    --phase acceptance --inspection_status no_correction_required





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


以下のコマンドは、``task_id.txt`` に記載されているタスクの内、担当者が未割当のタスクに対して受け入れ取り消ししています。


.. code-block::

    $ annofabcli task cancel_acceptance --project_id prj1 --task_id file://task_id.txt \
    --task_query '{"no_user":true}'


並列処理
----------------------------------------------

並列数4で実行します。

.. code-block::

    $  annofabcli task cancel_acceptance --project_id prj1 --task_id file://task.txt \
    --parallelism 4 --yes


