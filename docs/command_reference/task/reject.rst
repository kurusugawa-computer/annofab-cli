=================================
task reject
=================================

Description
=================================
タスクを差し戻します。
ただし作業中状態のタスクに対しては差し戻せません。





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

受入取り消しと差し戻しを同時に行う場合は、``--cancel_acceptance`` を指定してください。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt  --cancel_acceptance


差し戻す際に検査コメントを付与する場合は、``--comment`` を指定してください。
検査コメントの付与する場所は、``--comment_data`` で指定できます。後述を参照してください。


.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt \
     --comment "weather属性を見直してください。"

検査コメントの位置や区間を指定する
--------------------------------------
``--comment_data`` に、検査コメントの位置や区間をJSON形式で指定することができます。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id file://task_id.txt \
     --comment "weather属性を見直してください。" \
     --comment_data '{"x":10,"y":10,"_type":"Point"}'

``--comment_data`` に渡す形式は、https://annofab-cli.readthedocs.io/ja/latest/command_reference/inspection_comment/put_simply.html を参照してください。

``--comment_data`` を指定しない場合は、以下の検査コメントが付与されます。

* 画像プロジェクト： 点。先頭画像の左上に位置する。
* 動画プロジェクト： 区間。動画の先頭に位置する。
* カスタムプロジェクト（3dpc）： 辺が1の立方体。先頭フレームの原点に位置する。

ただし、ビルトインのエディタプラグインを使用していないカスタムプロジェクトの場合は ``--custom_project_type`` が必須です。

.. code-block::

    $ annofabcli task reject --project_id prj1 --task_id task1 \
     --comment "weather属性を見直してください。" \
     --custom_project_type 3dpc


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


補足
==================================================================

差し戻しタスクを再度教師付フェーズから提出した場合の、抜取受入/抜取検査
--------------------------------------------------------------------------------------------



``--comment`` 引数を指定して差し戻したタスクを、再度教師付フェーズから提出した場合、
そのタスクは `抜取受入率 <https://annofab.readme.io/docs/project-settings-task-settings#%E6%8A%9C%E5%8F%96%E5%8F%97%E5%85%A5%E7%8E%87>`_ / `抜取検査率 <https://annofab.readme.io/docs/project-settings-task-settings#%E6%8A%9C%E5%8F%96%E6%A4%9C%E6%9F%BB%E7%8E%87>`_ が適用されません。
確認すべき検査コメントが残っているためです。
たとえば抜取受入率/抜取検査率が0%でも、必ずスキップされません。


``--comment`` 引数を指定せずに差し戻したタスクを、再度教師付フェーズから提出した場合は、抜取受入率/抜取検査率が摘要されます。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.reject_tasks.add_parser
   :prog: annofabcli task reject
   :nosubcommands:
   :nodefaultconst:


