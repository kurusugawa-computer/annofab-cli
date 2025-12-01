====================================================================================
annotation_zip list_polygon_annotation
====================================================================================


Description
=================================
アノテーションZIPからポリゴンアノテーションの座標情報を出力します。

Annofabではポリラインとポリゴンの区別がないため、2点のみで構成されるポリラインも含まれる可能性があります。
その場合、面積、重心、外接矩形のサイズは ``null`` (NA) として扱われます。

Examples
=================================

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


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_polygon_annotation.add_parser
    :prog: annofabcli annotation_zip list_polygon_annotation
    :nosubcommands:
    :nodefaultconst:


