====================================================================================
annotation_zip list_3d_segment_annotation
====================================================================================


Description
=================================
アノテーションZIPから3次元セグメントアノテーションの情報を出力します。
1件のセグメントを1行として出力し、セグメントに含まれる点数も算出します。


Examples
=================================

基本的な使い方
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_segment_annotation --project_id prj1 --output out.csv


出力例（CSV形式）
----------------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_zip list_3d_segment_annotation --project_id prj1 \
     --output out.csv --format csv

.. csv-table:: out.csv
    :header-rows: 1
    :file: list_3d_segment_annotation/out.csv


出力例（JSON形式）
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_segment_annotation --project_id prj1 --output out.json --format pretty_json

.. code-block:: json
    :caption: out.json

    [
      {
        "project_id": "prj1",
        "task_id": "task1",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_id": "pointcloud1",
        "input_data_name": "pointcloud1.pcd",
        "updated_datetime": "2026-09-28T10:00:00+09:00",
        "label": "Road",
        "annotation_id": "01K67ABCDEF0123456789ABCDE",
        "annotation_editor_url": "https://example.com/3d-editor/#pointcloud1/01K67ABCDEF0123456789ABCDE",
        "data_uri": "./pointcloud1/01K67ABCDEF0123456789ABCDE",
        "point_count": 57746,
        "attributes": {
          "surface_type": "asphalt"
        }
      }
    ]


特定のラベルのみを出力
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_segment_annotation --project_id prj1 \
     --label_name Road Building --output out.csv


アノテーションZIPを直接指定
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_segment_annotation --annotation annotation.zip --output out.csv


出力項目について
=================================

* ``project_id``: プロジェクトID
* ``task_id``: タスクID
* ``task_status``: タスクステータス
* ``task_phase``: タスクフェーズ
* ``task_phase_stage``: タスクフェーズステージ
* ``input_data_id``: 入力データID
* ``input_data_name``: 入力データ名
* ``updated_datetime``: アノテーションJSONの更新日時
* ``label``: ラベル名
* ``annotation_id``: アノテーションID
* ``annotation_editor_url``: 対象のアノテーションを開く3次元エディタのURL
* ``data_uri``: 点インデックスを格納した外部ファイルの参照先
* ``point_count``: セグメントに含まれる点数。外部ファイルを読み込めない場合は ``null``
* ``attributes``: 属性。CSVでは ``attributes.<属性名>`` 列として出力


.. include:: task_metadata.inc

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_annotation_3d_segment.add_parser
    :prog: annofabcli annotation_zip list_3d_segment_annotation
