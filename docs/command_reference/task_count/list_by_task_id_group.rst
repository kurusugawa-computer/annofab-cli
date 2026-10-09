===================================
task_count list_by_task_id_group
===================================

Description
=================================

タスクIDのグループごとに、フェーズと状態別のタスク数などを横持ちのCSVまたはJSON形式で出力します。

``never_worked.unassigned`` と ``never_worked.assigned`` は ``never_worked`` に、
``worked.not_rejected`` と ``worked.rejected`` は ``worked`` にまとめます。
完了したタスクは ``acceptance.complete`` に集計します。


Examples
=================================

タスクIDのプレフィックスでグループ化
-----------------------------------------

``--task_id_delimiter`` に、タスクIDのプレフィックスと連番を分ける区切り文字を指定します。
たとえば、区切り文字が ``_`` の場合、タスクID ``aa_bb_001`` のグループは ``aa_bb`` です。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --task_id_delimiter _ --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :file: list_by_task_id_group/out.csv
   :header-rows: 1


グループ名に使用する要素数を指定
-----------------------------------------

``--task_id_group_component_count`` を指定すると、タスクIDを ``--task_id_delimiter`` で分割し、
先頭から指定した数の要素をグループ名として使用します。

たとえば、以下のコマンドではタスクID ``20260902_second_f00075528-00075822_cam5`` を
``20260902_second`` グループに集計します。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --task_id_delimiter _ \
        --task_id_group_component_count 2 --output out.csv

``--task_id_group_component_count`` を指定しない場合は、従来どおり末尾の要素だけを除いた
``20260902_second_f00075528-00075822`` がグループ名になります。


すべてのタスクを1グループとして集計
-----------------------------------------

タスクIDの命名規則にかかわらず、すべてのタスクをまとめて集計する場合は ``--single_group`` を指定します。
出力される ``task_id_group`` は ``all`` です。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --single_group --output out.csv


タスクIDとグループを個別に指定
-----------------------------------------

``--task_id_groups`` に、タスクIDグループをキー、タスクIDのリストを値とするJSON文字列を指定します。
どのグループにも指定されていないタスクは ``unknown`` に集計されます。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 \
        --task_id_groups '{"group1":["id1","id2"],"group2":["id3","id4"]}' \
        --output out.csv


入力データ数で集計
-----------------------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数を集計します。
``video_duration_hour`` または ``video_duration_minute`` を指定すると、動画プロジェクトの動画時間を集計します。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --task_id_delimiter _ \
        --unit input_data_count --output out.csv


JSON形式で出力
---------------------------------

``--format json`` または ``--format pretty_json`` を指定すると、CSVと同じ列名をキーにした
オブジェクトの配列を出力します。欠損値は ``null``、空の集計結果は ``[]`` になります。
省略時はCSV形式で出力します。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --task_id_delimiter _ --format pretty_json --output out.json

出力例（先頭の1行分）は次のとおりです。

.. code-block:: json

    [
      {
        "task_id_group": "train",
        "annotation.never_worked": 10,
        "annotation.worked": 20,
        "annotation.on_hold": 1,
        "inspection.never_worked": 5,
        "inspection.worked": 12,
        "inspection.on_hold": 0,
        "acceptance.never_worked": 3,
        "acceptance.worked": 8,
        "acceptance.on_hold": 1,
        "acceptance.complete": 40
      }
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_task_id_group.add_parser
   :prog: annofabcli task_count list_by_task_id_group
   :nosubcommands:
   :nodefaultconst:
