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

``--comment_data`` に渡す形式は、https://annofab.com/docs/api/#operation/batchUpdateInspections APIのリクエストボディ ``data`` を参照してください。

以下、サンプルです。

.. code-block::

    // 画像プロジェクト：(x=0,y=0)の位置に点
    {
        "x":0,
        "y":0,
        "_type": "Point"
    }

    // 動画プロジェクト：0〜100ミリ秒の区間
    {
        "start":0,
        "end":100,
        "_type": "Time"
    }

    // カスタムプロジェクト（3dpc editor）：原点付近に辺が1の立方体
    {
        "data": "{\"kind\": \"CUBOID\", \"shape\": {\"dimensions\": {\"width\": 1.0, \"height\": 1.0, \"depth\": 1.0}, \"location\": {\"x\": 0.0, \"y\": 0.0, \"z\": 0.0}, \"rotation\": {\"x\": 0.0, \"y\": 0.0, \"z\": 0.0}, \"direction\": {\"front\": {\"x\": 1.0, \"y\": 0.0, \"z\": 0.0}, \"up\": {\"x\": 0.0, \"y\": 0.0, \"z\": 1.0}}}, \"version\": \"2\"}",
        "_type": "Custom"    
    }


``--comment_data`` を指定しない場合は、以下の値になります。

* 画像プロジェクト： ``{"x":0, "y":0, "_type": "Point"}``
* 動画プロジェクト： ``{"start":0, "end":100, "_type": "Time"}``

カスタムプロジェクトの場合は、検査コメントの位置を決められないので、 ``--comment_data`` は必須です。


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

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.reject_tasks.add_parser
   :prog: annofabcli task reject
   :nosubcommands:
