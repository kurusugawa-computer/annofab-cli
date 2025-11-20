==========================================
statistics list_annotation_area
==========================================

Description
=================================

アノテーションzipまたはディレクトリに含まれる以下のアノテーションの面積を出力します。

* 矩形
* ポリゴン
* 塗りつぶしv1（インスタンスセグメンテーション）
* 塗りつぶしv2（セマンティックセグメンテーション）


.. note::

    AnnofabのアノテーションZIPでは、ポリゴンとポリラインの区別がないため、ポリラインアノテーションも出力されます。
    
    



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
        "updated_datetime": "2023-10-01T12:00:00.000+09:00",
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

