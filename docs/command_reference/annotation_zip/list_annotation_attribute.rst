==================================================
annotation_zip list_annotation_attribute
==================================================


Description
=================================

アノテーションZIPを読み込み、アノテーションの属性値の一覧を出力します。
各アノテーションごとに、ラベル名と属性値を1件ずつ出力します。


Examples
=================================


JSON出力
--------------------------


.. code-block::

    $ annofabcli annotation_zip list_annotation_attribute --project_id prj1 \
     --output out.json --format pretty_json


.. code-block:: json
    :caption: out.json

    [
        {
            "project_id": "project1",
            "task_id": "task1",
            "task_status": "not_started",
            "task_phase": "annotation",
            "task_phase_stage": 1,
            "input_data_id": "input_data1",
            "input_data_name": "input_data1",
            "updated_datetime": "2023-10-01T12:00:00.000+09:00",
            "annotation_id": "7c113d44-d927-4457-a1c5-45ba6e34bbc4",
            "label": "car",
            "attributes": {
                "occluded": true,
                "type": "sedan"
            }
        }
    ]


CSV出力
--------------------------

CSVでは、属性値は ``attributes.occluded`` や ``attributes.type`` のように ``attributes.<属性名>`` という列名で出力されます。

.. code-block::

    $ annofabcli annotation_zip list_annotation_attribute --project_id prj1 \
     --output out.csv --format csv

.. csv-table:: out.csv
    :header-rows: 1
    :file: list_annotation_attribute/out.csv


ローカルのアノテーションZIPを読み込む
------------------------------------------

``--annotation`` を指定すると、ローカルのアノテーションZIPまたはZIPを展開したディレクトリを読み込めます。

.. code-block::

    $ annofabcli annotation_zip list_annotation_attribute --annotation annotation.zip \
     --output out.csv --format csv


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.list_annotation_attribute.add_parser
   :prog: annofabcli annotation_zip list_annotation_attribute
   :nosubcommands:
   :nodefaultconst:
