==========================================
annotation_zip count_annotation_by_label
==========================================

Description
=================================

ラベルごとにアノテーション数を出力します。

アノテーション数は、ダウンロードしたアノテーションZIPから算出します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 --output out.json --format pretty_json

.. code-block:: json
    :caption: out.json

    [
    {
        "annotation_count": 130,
        "annotation_count_by_label": {
            "car": 60,
            "bike": 10
        },
        "project_id": "project1",
        "task_id": "task1",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_count": 10
    }
    ]

デフォルトではタスク単位でアノテーション数を集計します。入力データ単位に集計する場合は、 ``--group_by input_data_id`` を指定してください。

``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 --annotation annotation.zip --output out.csv


CSV出力
--------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_label --project_id prj1 --group_by task_id --output out_by_task_label.csv

``--group_by input_data_id`` を指定すると、入力データごとラベルごとのアノテーション数を出力します。


Command line options
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.count_annotation_by_label.add_parser
   :prog: annofabcli annotation_zip count_annotation_by_label
   :nosubcommands:
