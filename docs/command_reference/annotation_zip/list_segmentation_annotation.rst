====================================================================================
annotation_zip list_segmentation_annotation
====================================================================================


Description
=================================
アノテーションZIPから塗りつぶしアノテーションの情報を出力します。

対象のアノテーション種類は ``Segmentation`` と ``SegmentationV2`` です。

Examples
=================================

基本的な使い方
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_segmentation_annotation --project_id prj1 --output out.json --format pretty_json



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
        "annotation_editor_url": "https://annofab.com/projects/proj1/tasks/task_00/editor?#i1/ann1",
        "annotation_type": "Segmentation",
        "data_uri": "ann1",
        "area": 1200,
        "bounding_box": {
          "left_top": {"x": 10, "y": 20},
          "right_bottom": {"x": 59, "y": 43}
        },
        "bounding_box_width": 50,
        "bounding_box_height": 24,
        "attributes": {
          "visible": true
        }
      }
    ]


特定のラベルのみ出力
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_segmentation_annotation --project_id prj1 --label_name road sky --output out.csv



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
* ``annotation_editor_url`` : アノテーションエディタのURL。対象のアノテーションを直接開くことができます。

塗りつぶしアノテーション情報
----------------------------------------

* ``annotation_type`` : アノテーションの種類。 ``Segmentation`` または ``SegmentationV2``
* ``data_uri`` : 塗りつぶし画像の外部ファイルを参照するURI
* ``area`` : 塗りつぶし領域の面積。単位はピクセル数です。外部ファイルを読み込めない場合は ``null`` です。
* ``bounding_box`` : 塗りつぶし領域の外接矩形。 ``left_top`` と ``right_bottom`` を持ちます。外部ファイルを読み込めない場合や面積が0の場合は ``null`` です。
* ``bounding_box_width`` : 外接矩形の幅。外部ファイルを読み込めない場合や面積が0の場合は ``null`` です。
* ``bounding_box_height`` : 外接矩形の高さ。外部ファイルを読み込めない場合や面積が0の場合は ``null`` です。

属性情報
--------------------

* ``attributes`` : 属性情報。JSON形式ではオブジェクト、CSV形式では ``attributes.属性名`` の形式で列が追加されます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_segmentation_annotation.add_parser
    :prog: annofabcli annotation_zip list_segmentation_annotation
    :nosubcommands:
    :nodefaultconst:
