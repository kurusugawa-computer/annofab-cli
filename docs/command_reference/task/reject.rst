=================================
task reject
=================================

Description
=================================
タスクを差し戻します。
ただし作業中状態のタスクに対しては差し戻せません。

``annofabcli task reject`` コマンドで差し戻したタスクは、画面から差し戻したタスクとは異なり、抜取検査・抜取受入のスキップ判定に影響を及ぼしません。




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


以下のコマンドは、``--task_id`` に指定したタスクを差し戻します。差し戻したタスクは教師付フェーズになり、担当者は最後の教師付フェーズを担当したユーザになります。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt

完了状態のタスクを差し戻すには、先に受入取り消し（`annofabcli task cancel_acceptance <../task/cancel_acceptance.html>`_）を実行する必要があります。
受入取り消しと差し戻しを同時に行う場合は、``--cancel_acceptance`` を指定してください。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt  --cancel_acceptance


差し戻す際に検査コメントを付与する場合は、``--comment`` を指定してください。
検査コメントの付与する場所は、以下の通りです。

* 画像プロジェクト: 1番目の画像の左上( ``x=0, y=0`` )
* 動画プロジェクト: 動画の先頭( ``start=0, end=100`` )


.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt \
     --comment "weather属性を見直してください。"



差し戻したタスクの担当者を指定する
--------------------------------------

差し戻したタスクの担当者は、デフォルトでは最後の教師付フェーズを担当したユーザになります。
担当者を指定する場合は、``--assigned_annotator_user_id`` に担当させたいユーザのuser_idを指定してください。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://tasks.txt \
    --assigned_annotator_user_id user1

担当者を割り当てない場合は ``--not_assign`` を指定してください。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://tasks.txt \
    --not_assign





タスクのフェーズやステータスなどで絞り込む
----------------------------------------------
``--task_query`` を指定すると、タスクのフェーズやステータスなどで、操作対象のタスクを絞り込むことができます。


以下のコマンドは、``task_id.txt`` に記載されているタスクの内、受入フェーズで未着手のタスクを差し戻します。


.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt \
     --task_query '{"phase":"acceptance", "status:"not_started"}' 



並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli task reject --project_id prj1 --task_id file://task.txt \
    --parallelism 4 --yes



