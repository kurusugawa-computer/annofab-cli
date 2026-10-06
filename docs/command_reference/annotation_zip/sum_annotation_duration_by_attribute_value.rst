================================================================================
annotation_zip sum_annotation_duration_by_attribute_value
================================================================================

Description
=================================

属性値ごとに区間アノテーションの長さを合計し、動画長とともに秒単位で出力します。

デフォルトは選択肢系の属性（ドロップダウン、ラジオボタン、チェックボックス）を集計します。
``--additional_attribute_name`` は指定属性を追加し、 ``--attribute_name`` は指定属性だけを対象にします。両者は排他です。
``--label_name`` と併用すると、ラベルと属性の両方に一致する属性値を対象にします。
詳細は :doc:`count_annotation_by_attribute_value` を参照してください。

属性値CSVはラベル名・属性名・属性値の3行ヘッダーです。
同じ区間が複数の属性に計上されるため、属性値集計では総合計の ``annotation_duration_second`` を出力しません。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_attribute_value --project_id prj1 --output out.csv

.. csv-table:: out.csv
   :file: sum_annotation_duration_by_attribute_value/out.csv
   :header-rows: 3

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_attribute_value --project_id prj1 --format pretty_json --output out.json

.. code-block:: json

    [
      {
        "project_id": "prj1",
        "task_id": "task1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_id": "video1",
        "input_data_name": "video1.mp4",
        "updated_datetime": "2026-10-06T12:00:00+09:00",
        "video_duration_second": 60.0,
        "annotation_duration_second_by_attribute_value": {
          "speech": {"speaker": {"male": 12.0, "female": 8.0}}
        }
      }
    ]

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_attribute_value --project_id prj1 \
      --annotation annotation.zip --output by_task.csv

.. code-block:: bash

    $ annofabcli annotation_zip sum_annotation_duration_by_attribute_value --project_id prj1 \
      --group_by task_phase task_status --output summary.csv

.. include:: sum_annotation_duration.inc

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.sum_annotation_duration_by_attribute_value.add_parser
   :prog: annofabcli annotation_zip sum_annotation_duration_by_attribute_value
   :nosubcommands:
