==================================================
annotation delete_per_annotation
==================================================

Description
=================================
``task_id``、``input_data_id``、``annotation_id`` の一覧で指定したアノテーションを削除します。

作業中状態のタスクは削除できません。完了状態のタスクも削除するには、``--include_complete_task`` を指定してください。

削除前のバックアップを保存するには、``--backup`` を指定してください。
復元方法は `annotation restore <restore.html>`_ を参照してください。

Examples
=================================

CSVに ``annotation_id`` を指定して削除する
----------------------------------------------------

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり


.. csv-table::
   :header: 列名,必須,備考

    task_id,Yes,
    input_data_id,Yes,
    annotation_id,Yes,


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: annotation.csv

    task_id,input_data_id,annotation_id
    t1,i1,a1
    t1,i1,a2
    t2,i2,a3


.. code-block::

    $ annofabcli annotation delete_per_annotation --project_id p1 --csv annotation.csv --backup backup_dir/


``annotation_id`` をJSON形式で指定して削除する
----------------------------------------------------

以下は、JSONファイルのサンプルです。


.. code-block::
    :caption: annotation.json

    [
        {
            "task_id": "t1",
            "input_data_id":"i1",
            "annotation_id": "a1"
        }
    ]


JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli annotation delete_per_annotation --project_id p1 --json file://annotation.json --backup backup_dir/


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.delete_annotation_per_annotation.create_parser
    :prog: annofabcli annotation delete_per_annotation
    :nosubcommands:
    :nodefaultconst:

See also
=================================
* `annotation delete <delete.html>`_
* `annotation restore <restore.html>`_
