=========================
task_count list_by_phase
=========================

Description
=================================
フェーズごとのタスク数を出力します。

タスクの状態は以下の6つのカテゴリに分類されます。

* ``never_worked.unassigned``: 一度も作業していない状態かつ担当者未割り当て
* ``never_worked.assigned``: 一度も作業していない状態かつ担当者割り当て済み
* ``worked.not_rejected``: 作業中または休憩中で、まだ差し戻されていない
* ``worked.rejected``: 作業中または休憩中で、次のフェーズで差し戻された
* ``on_hold``: 保留中
* ``complete``: 完了


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドで、フェーズごとのタスク数を出力します。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --output out.csv


作業時間の閾値を指定
--------------------------

``--not_worked_threshold_second`` で作業していないとみなす作業時間の閾値を指定できます。
例えば、60秒以下の作業時間のタスクを未着手とみなす場合は以下のようにします。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --not_worked_threshold_second 60 --output out.csv


メタデータキーでグループ化
--------------------------

``--metadata_key`` でメタデータのキーを指定すると、そのキーの値でグループ化して集計します。
複数のキーを指定することもできます。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --metadata_key dataset_type category --output out.csv


出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --output out.csv

``out.csv`` の出力例：

.. code-block::
    :caption: out.csv

    phase,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete
    annotation,10,5,8,2,1,74
    inspection,0,0,12,3,0,85
    acceptance,0,0,8,0,0,92


メタデータキーを指定した場合の出力例：

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --metadata_key dataset_type --output out.csv

.. code-block::
    :caption: out.csv

    phase,metadata.dataset_type,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete
    annotation,train,8,3,5,1,1,42
    annotation,validation,2,2,3,1,0,32
    inspection,train,0,0,8,2,0,48
    inspection,validation,0,0,4,1,0,37
    acceptance,train,0,0,5,0,0,53
    acceptance,validation,0,0,3,0,0,39


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_phase.add_parser
   :prog: annofabcli task_count list_by_phase
   :nosubcommands:
   :nodefaultconst:
