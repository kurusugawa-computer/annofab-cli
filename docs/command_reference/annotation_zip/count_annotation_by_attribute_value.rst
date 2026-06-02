==================================================
annotation_zip count_annotation_by_attribute_value
==================================================

Description
=================================

属性値ごとにアノテーション数を出力します。

アノテーション数は、ダウンロードしたアノテーションZIPから算出します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_attribute_value --project_id prj1 --output out.json --format pretty_json

.. code-block:: json
    :caption: out.json

    [
    {
        "annotation_count": 130,
        "annotation_count_by_attribute_value": {
            "car": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                },
                "type": {
                    "normal": 10,
                    "bus": 20
                }
            },
            "bike": {
                "occlusion": {
                    "false": 10,
                    "true": 20
                }
            }
        },
        "project_id": "project1",
        "task_id": "task1",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "task_status": "complete",
        "input_data_count": 10
    }
    ]

集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス

上記以外の属性（数値、テキストなど）を集計したい場合は、 ``--additional_attribute_name`` または ``--attribute_name`` オプションを使用してください。

* ``--additional_attribute_name`` : デフォルトの選択肢系属性に加えて、指定した属性を集計対象にします。
* ``--attribute_name`` : 指定した属性のみを集計対象にします（デフォルトの選択肢系属性は含まれません）。

デフォルトではタスク単位でアノテーション数を集計します。入力データ単位に集計する場合は、 ``--group_by input_data_id`` を指定してください。

``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_attribute_value --project_id prj1 --annotation annotation.zip --output out.csv


CSV出力
--------------------------

.. code-block::

    $ annofabcli annotation_zip count_annotation_by_attribute_value --project_id prj1 --group_by task_id --output out_by_task_attribute_value.csv

``--group_by input_data_id`` を指定すると、入力データごと属性値ごとのアノテーション数を出力します。


Command line options
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.count_annotation_by_attribute_value.add_parser
   :prog: annofabcli annotation_zip count_annotation_by_attribute_value
   :nosubcommands:
