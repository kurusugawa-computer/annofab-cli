====================================================================================
annotation_zip list_polygon_annotation
====================================================================================


Description
=================================
アノテーションZIPからポリゴンアノテーションの座標情報と属性情報を出力します。

Annofabではポリラインとポリゴンの区別がないため、ポリラインも含まれる可能性があります。



Examples
=================================

基本的な使い方
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_polygon_annotation --project_id prj1 --output out.json --format pretty_json



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
        "input_data_name": "i1.jpg",
        "updated_datetime": "2023-10-01T12:00:00.000+09:00",
        "label": "cat",
        "annotation_id": "ann1",
        "point_count": 3,
        "area": 50.0,
        "centroid": {"x": 3.3, "y": 3.3},
        "bounding_box_width": 10,
        "bounding_box_height": 10,
        "attributes": {
          "occluded": true,
          "type": "sedan"
        },
        "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]
      }
    ]







特定のラベルのみ出力
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_polygon_annotation --project_id prj1 --label_name cat dog --output out.csv





出力項目について
=================================

基本情報
--------------------

* ``project_id`` : プロジェクトID
* ``task_id`` : タスクID
* ``task_status`` : タスクのステータス（not_started, working, complete, など）
* ``task_phase`` : タスクのフェーズ（annotation, inspection, acceptance）
* ``task_phase_stage`` : タスクのフェーズステージ（1から始まる整数）
* ``input_data_id`` : 入力データID
* ``input_data_name`` : 入力データ名
* ``updated_datetime`` : アノテーションJSONの更新日時（ISO 8601形式）
* ``label`` : ラベル名
* ``annotation_id`` : アノテーションID

ポリゴン情報
--------------------

* ``point_count`` : ポリゴンの頂点数
* ``area`` : ポリゴンの面積
* ``centroid`` : ポリゴンの重心（x, y）
* ``bounding_box_width`` : 外接矩形の幅
* ``bounding_box_height`` : 外接矩形の高さ
* ``points`` : ポリゴンの頂点リスト

属性情報
--------------------

* ``attributes`` : 属性情報。JSON形式ではオブジェクト、CSV形式では ``attributes.属性名`` の形式で列が追加されます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_polygon_annotation.add_parser
    :prog: annofabcli annotation_zip list_polygon_annotation
    :nosubcommands:
    :nodefaultconst:


