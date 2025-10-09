====================================================================================
annotation_zip list_single_point_annotation
====================================================================================


Description
=================================
アノテーションZIPから点アノテーションの座標情報を出力します。

Examples
=================================

.. code-block:: bash


    $ annofabcli annotation_zip list_single_point_annotation --project_id prj1 --output out.json --format pretty_json



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
        "point": {"x": 0, "y": 0}
      }
    ]


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_single_point_annotation.add_parser
    :prog: annofabcli annotation_zip list_single_point_annotation
    :nosubcommands:
    :nodefaultconst: