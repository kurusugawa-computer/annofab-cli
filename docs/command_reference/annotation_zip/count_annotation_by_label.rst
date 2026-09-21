==========================================
annotation_zip count_annotation_by_label
==========================================

Description
=================================

ラベルごとにアノテーション数を出力します。

アノテーション数は、ダウンロードしたアノテーションZIPから算出します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 --output out.json --format pretty_json

.. code-block:: json
    :caption: out.json

    [
    {
        "annotation_count_by_label": {
            "car": 60,
            "bike": 10
        },
        "project_id": "project1",
        "task_id": "task1",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_count": 10
    }
    ]

デフォルトではタスク単位でアノテーション数を集計します。入力データ単位に集計する場合は、 ``--group_by input_data_id`` を指定してください。

``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 --annotation annotation.zip --output out.csv


CSV出力
--------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 --group_by task_id --output out_by_task_label.csv

デフォルトの ``--group_by task_id`` では、1行が1タスクを表します。ラベルの英語名が列名になり、アノテーション仕様に定義されているラベルは、対象アノテーションがなくても列として出力されます。

.. csv-table:: out_by_task.csv
   :file: count_annotation_by_label/out_by_task.csv

``--group_by input_data_id`` を指定すると、1行が1入力データを表します。 ``input_data_id`` 、 ``input_data_name`` 、 ``frame_no`` 、 ``updated_datetime`` 列が追加され、 ``input_data_count`` 列は出力されません。

.. csv-table:: out_by_input_data.csv
   :file: count_annotation_by_label/out_by_input_data.csv

各列の意味は以下のとおりです。

* ``project_id``: プロジェクトID
* ``task_id``: タスクID
* ``task_phase``: タスクフェーズ
* ``task_phase_stage``: タスクフェーズの段階
* ``task_status``: タスクステータス
* ``input_data_count``: タスクに含まれる入力データ数（ ``--group_by task_id`` の場合のみ）
* ``input_data_id``: 入力データID（ ``--group_by input_data_id`` の場合のみ）
* ``input_data_name``: 入力データ名（ ``--group_by input_data_id`` の場合のみ）
* ``frame_no``: タスク内における入力データの順番（1始まり）（ ``--group_by input_data_id`` の場合のみ）
* ``updated_datetime``: アノテーションJSONの更新日時（ ``--group_by input_data_id`` の場合のみ）
* ``<label_name>``: ラベルの英語名ごとのアノテーション数

入力データあたりのアノテーション数を出力する
--------------------------------------------------

.. include:: with_per_input_data.inc

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 \
      --group_by task_id --with_per_input_data --output out_by_task_label.csv

追加される列名は ``per_input_data.<label_name>`` 形式です。


Command line options
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.count_annotation_by_label.add_parser
   :prog: annofabcli annotation_zip count_annotation_by_label
   :nosubcommands:
