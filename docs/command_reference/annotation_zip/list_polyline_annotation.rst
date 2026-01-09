====================================================================================
annotation_zip list_polyline_annotation
====================================================================================


Description
=================================
アノテーションZIPからポリラインアノテーションの座標情報と属性情報を出力します。

Annofabではポリラインとポリゴンの区別がないため、ポリゴンも含まれる可能性があります。



Examples
=================================

基本的な使い方
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_polyline_annotation --project_id prj1 --output out.json --format pretty_json



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
        "label": "road",
        "annotation_id": "ann1",
        "point_count": 5,
        "length": 100.5,
        "start_point": {"x": 10.0, "y": 20.0},
        "end_point": {"x": 50.0, "y": 80.0},
        "midpoint": {"x": 30.0, "y": 45.0},
        "bounding_box_width": 40.0,
        "bounding_box_height": 60.0,
        "attributes": {
          "type": "dashed",
          "color": "white"
        },
        "points": [{"x": 10, "y": 20}, {"x": 20, "y": 30}, {"x": 30, "y": 45}, {"x": 40, "y": 60}, {"x": 50, "y": 80}]
      }
    ]







特定のラベルのみ出力
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_polyline_annotation --project_id prj1 --label_name road lane --output out.csv





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

ポリライン情報
--------------------

* ``point_count`` : ポリラインの頂点数
* ``length`` : ポリラインの総長（各線分の長さの合計、単位はピクセル）
* ``start_point`` : 始点の座標（x, y）
* ``end_point`` : 終点の座標（x, y）
* ``midpoint`` : 中点（全頂点の座標平均、x, y）
* ``bounding_box_width`` : 外接矩形の幅（単位はピクセル）
* ``bounding_box_height`` : 外接矩形の高さ（単位はピクセル）
* ``points`` : ポリラインの頂点リスト

属性情報
--------------------

``attributes`` 配下に、アノテーションに設定された属性情報が含まれます。
CSV出力時は ``attributes.<属性名>`` の形式で列が作成されます。




See also
=================================

* :doc:`list_polygon_annotation`




Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_polyline_annotation.add_parser
    :prog: annofabcli annotation_zip list_polyline_annotation
    :nosubcommands:
    :nodefaultconst:
