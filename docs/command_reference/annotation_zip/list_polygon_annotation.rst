====================================================================================
annotation_zip list_polygon_annotation
====================================================================================


Description
=================================
アノテーションZIPからポリゴンアノテーションの座標情報と属性情報を出力します。

Annofabではポリラインとポリゴンの区別がないため、ポリラインも含まれる可能性があります。


Output Format
=================================

CSV/JSON/PRETTY_JSON形式で出力できます。CSV形式では、ネストした辞書が展開されて出力されます。

出力される項目
--------------------

基本情報
^^^^^^^^^^^^

* ``project_id`` : プロジェクトID
* ``task_id`` : タスクID
* ``task_status`` : タスクのステータス（not_started, working, complete, など）
* ``task_phase`` : タスクのフェーズ（annotation, inspection, acceptance）
* ``task_phase_stage`` : タスクのフェーズステージ（1から始まる整数）
* ``input_data_id`` : 入力データID
* ``input_data_name`` : 入力データ名
* ``updated_datetime`` : アノテーションの更新日時（ISO 8601形式）
* ``label`` : ラベル名
* ``annotation_id`` : アノテーションID

ポリゴン情報
^^^^^^^^^^^^

* ``point_count`` : ポリゴンの頂点数
* ``area`` : ポリゴンの面積（2点以下のポリラインの場合はNone）
* ``centroid.x`` : ポリゴンの重心のX座標（2点以下のポリラインの場合はNone）
* ``centroid.y`` : ポリゴンの重心のY座標（2点以下のポリラインの場合はNone）
* ``bounding_box_width`` : 外接矩形の幅（2点以下のポリラインの場合はNone）
* ``bounding_box_height`` : 外接矩形の高さ（2点以下のポリラインの場合はNone）
* ``points`` : ポリゴンの頂点リスト（JSON/PRETTY_JSON形式のみ。各頂点は ``{"x": int, "y": int}`` の形式）

属性情報
^^^^^^^^^^^^

* ``attributes.<属性名>`` : アノテーションの属性値。CSV形式では ``attributes.`` のプレフィックス付きで各属性が別々の列として出力されます。
  JSON/PRETTY_JSON形式では ``attributes`` オブジェクトとして出力されます。

.. note::

   CSV形式では ``points`` 列は含まれません（列の長さが非常に大きくなるため）。
   座標情報が必要な場合はJSON形式で出力してください。


Examples
=================================

基本的な使い方
--------------------

JSON形式で出力
^^^^^^^^^^^^

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


CSV形式で出力
^^^^^^^^^^^^

.. code-block:: bash

    $ annofabcli annotation_zip list_polygon_annotation --project_id prj1 --output out.csv --format csv


CSV形式では、 ``centroid`` と ``attributes`` が展開されて列として出力されます。
たとえば、上記のJSON例と同じデータをCSV形式で出力すると以下のようになります。

.. csv-table::
   :header: "project_id", "task_id", "...", "centroid.x", "centroid.y", "...", "attributes.occluded", "attributes.type"
   :widths: 10, 10, 5, 10, 10, 5, 15, 15

   "proj1", "task_00", "...", 3.3, 3.3, "...", true, "sedan"


特定のラベルのみ出力
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_polygon_annotation --project_id prj1 --label_name cat dog --output out.csv


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_polygon_annotation.add_parser
    :prog: annofabcli annotation_zip list_polygon_annotation
    :nosubcommands:
    :nodefaultconst:


