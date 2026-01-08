====================================================================================
annotation_zip list_3d_bounding_box_annotation
====================================================================================


Description
=================================
アノテーションZIPから3Dバウンディングボックス（CUBOID）アノテーションの座標情報を出力します。


Examples
=================================

基本的な使い方
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_bounding_box_annotation --project_id prj1 --output out.csv


出力例（JSON形式）
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_bounding_box_annotation --project_id prj1 --output out.json --format pretty_json


.. code-block:: json
    :caption: out.json

    [
      {
        "project_id": "proj1",
        "task_id": "task_00",
        "task_status": "complete",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "input_data_id": "i1",
        "input_data_name": "i1.bin",
        "updated_datetime": "2023-10-01T12:00:00.000+09:00",
        "label": "car",
        "annotation_id": "ann1",
        "dimensions": {
          "width": 2.39,
          "height": 1.56,
          "depth": 5.16
        },
        "location": {
          "x": -0.32,
          "y": 13.09,
          "z": 0.71
        },
        "rotation": {
          "x": 0,
          "y": 0,
          "z": 4.71
        },
        "direction": {
          "front": {
            "x": 0,
            "y": -1,
            "z": 0
          },
          "up": {
            "x": 0,
            "y": 0,
            "z": 1
          }
        },
        "volume": 19.3,
        "footprint_area": 12.3,
        "bottom_z": -0.06,
        "top_z": 1.49,
        "attributes": {
          "occluded": true,
          "type": "sedan"
        }
      }
    ]


特定のラベルのみを出力
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_bounding_box_annotation --project_id prj1 \
     --label_name car truck --output out.csv


アノテーションZIPを直接指定
----------------------------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_3d_bounding_box_annotation --annotation annotation.zip --output out.csv


出力項目について
=================================

CSVまたはJSON形式で以下の項目が出力されます。

基本情報
----------------------------------------------------------------------
* project_id: プロジェクトID
* task_id: タスクID
* task_status: タスクステータス
* task_phase: タスクフェーズ
* task_phase_stage: タスクフェーズステージ
* input_data_id: 入力データID
* input_data_name: 入力データ名
* updated_datetime: アノテーションJSONの更新日時
* label: ラベル名
* annotation_id: アノテーションID

3Dバウンディングボックス情報
----------------------------------------------------------------------

アノテーションJSONと同様の形式で出力されます。

* dimensions: サイズ情報（width, height, depth）
* location: 中心座標（x, y, z）
* rotation: 回転情報（x=roll, y=pitch, z=yaw）
* direction: 方向ベクトル（front, up）。CSV形式では出力されません


追加情報
----------------------------------------------------------------------
アノテーションJSONに含まれていない以下の項目も出力されます。

* volume: 体積（width × height × depth）
* footprint_area: 底面積（width × depth）。地面占有面積。
* bottom_z: 底面のZ座標（location.z - height/2）。回転は考慮していない。
* top_z: 天面のZ座標（location.z + height/2）。回転は考慮していない。


属性情報
----------------------------------------------------------------------
* attributes: 属性情報。JSON形式ではオブジェクト、CSV形式では ``attributes.属性名`` の形式で列が追加されます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_annotation_3d_bounding_box.add_parser
    :prog: annofabcli annotation_zip list_3d_bounding_box_annotation
    :nosubcommands:
    :nodefaultconst:
