==========================================
statistics list_annotation_area
==========================================

Description
=================================

アノテーションzipまたはディレクトリに含まれる、塗りつぶしアノテーションまたは矩形アノテーションの面積を、アノテーションごとに出力します。

Examples
=================================


.. code-block::

    $ annofabcli statistics list_annotation_area --project_id prj1 \
     --output out.json --format pretty_json

.. code-block:: json
    :caption: out.json

    [
      {
        "task_id": "task_00",
        "task_status": "complete",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "input_data_id": "i1",
        "input_data_name": "i1.jpg",
        "label": "cat",
        "annotation_id": "ann1",
        "annotation_area": 1234
      },
    ]



Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_annotation_area.add_parser
   :prog: annofabcli statistics list_annotation_area
   :nosubcommands:
   :nodefaultconst:

