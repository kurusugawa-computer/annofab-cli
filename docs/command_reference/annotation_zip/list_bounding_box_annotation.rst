====================================================================================
annotation_zip list_bounding_box_annotation
====================================================================================


Description
=================================
アノテーションZIPからバウンディングボックス（矩形）アノテーションの座標情報を出力します。

Examples
=================================

.. code-block:: bash


    $ annofabcli annotation_zip list_bounding_box_annotation --project_id prj1 --output out.json --format pretty_json



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
        "left_top": {"x": 0, "y": 0},
        "right_bottom": {"x": 100, "y": 200},
        "center": {"x": 50.0, "y": 100.0},
        "width": 100,
        "height": 200,
        "area": 20000,
        "attributes": {
          "occluded": true,
          "confidence": 0.95
        }
      }
    ]


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_annotation_bounding_box_2d.add_parser
    :prog: annofabcli annotation_zip list_bounding_box_annotation
    :nosubcommands:
    :nodefaultconst:


