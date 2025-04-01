==================================================
statistics list_annotation_attribute_filled_count
==================================================

Description
=================================

アノテーションZIPを読み込み、属性が空でないアノテーションの個数を出力します。

Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli statistics list_annotation_attribute_filled_count --project_id prj1 --output out.json --format pretty_json

.. code-block:: json
    :caption: out.json

    [
    {
        "task_id": "task1",
        "input_data_id": "input_data1",
        "filled_annotation_count": 5
    }
    ]

* ``filled_annotation_count`` : 属性が空でないアノテーションの個数

CSV出力
--------------------------

.. code-block::

    $ annofabcli statistics list_annotation_attribute_filled_count --project_id prj1 --output out.csv --format csv

.. csv-table:: out.csv
    :header-rows: 1
    :file: list_annotation_attribute_filled_count/out.csv

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_annotation_attribute_filled_count.add_parser
   :prog: annofabcli statistics list_annotation_attribute_filled_count
   :nosubcommands:
   :nodefaultconst:
