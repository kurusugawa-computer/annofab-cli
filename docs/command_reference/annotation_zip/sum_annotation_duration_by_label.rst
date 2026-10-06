================================================================================
annotation_zip sum_annotation_duration_by_label
================================================================================

Description
=================================

ラベルごとに区間アノテーションの長さを合計し、動画長とともに秒単位で出力します。

``--label_name`` でラベルを絞り込めます。 ``annotation_duration_second`` は対象ラベル列の合計です。
ラベルCSVは1行ヘッダーで、ラベル名が列名です。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_label --project_id prj1 --output out.csv

.. csv-table:: out.csv
   :file: sum_annotation_duration_by_label/out.csv
   :header-rows: 1

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_label --project_id prj1 --format pretty_json --output out.json

.. code-block:: json

    [
      {
        "project_id": "prj1",
        "task_id": "task1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_count": 1,
        "video_duration_second": 60.0,
        "annotation_duration_second": 30.0,
        "annotation_duration_second_by_label": {"speech": 20.0, "music": 10.0}
      }
    ]

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_label --project_id prj1 \
      --annotation annotation.zip --group_by input_data_id --output by_input.csv

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_label --project_id prj1 \
      --group_by task_phase task_status --output summary.csv

入力データ単位では ``input_data_id``、 ``input_data_name``、 ``frame_no``、 ``updated_datetime`` が追加され、
``input_data_count`` は出力されません。サマリーには集計キー、 ``task_count``、 ``input_data_count`` を出力します。

.. include:: sum_annotation_duration.inc

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.sum_annotation_duration_by_label.add_parser
   :prog: annofabcli annotation_zip sum_annotation_duration_by_label
   :nosubcommands:
