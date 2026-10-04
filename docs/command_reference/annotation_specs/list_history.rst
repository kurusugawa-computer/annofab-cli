==========================================
annotation_specs list_history
==========================================

Description
=================================
アノテーション仕様の履歴一覧を出力します。




Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_specs list_history --project_id prj1 


.. _annotation-specs-history-selection:

過去のアノテーション仕様を指定する
----------------------------------------------

アノテーション仕様を参照するコマンドでは、 ``--history_id`` 、 ``--before`` 、 ``--updated_datetime`` のいずれかを指定できます。
いずれも指定しない場合は、最新のアノテーション仕様を参照します。

``--updated_datetime`` には、ISO 8601形式の日付または日時を指定します。
タイムゾーンを省略した場合はJSTとして扱います。

.. code-block:: bash

    $ annofabcli annotation_specs export --project_id prj1 --updated_datetime 2025-03-07
    $ annofabcli annotation_specs export --project_id prj1 --updated_datetime 2025-03-07T14:30:15+09:00

日付を指定した場合はその日、分まで指定した場合はその1分間のように、指定した精度で履歴を検索します。
該当する履歴が複数存在する場合は候補の ``updated_datetime`` と ``history_id`` が表示されるので、日時を詳細にするか ``--history_id`` を指定してください。



出力結果
=================================


CSV出力
----------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_specs list_history --project_id prj1 --format csv --output out.csv

.. csv-table:: out.csv
    :file: list_history/out.csv
    :header-rows: 1

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_history --project_id prj1  --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "history_id": "1609907377",
            "project_id": "prj1",
            "updated_datetime": "2021-01-06T13:29:37.612+09:00",
            "url": "https://annofab.com/projects/...",
            "account_id": "account1",
            "comment": null,
            "user_id": "user1",
            "username": "username1"
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_history.add_parser
   :prog: annofabcli annotation_specs list_history
   :nosubcommands:
   :nodefaultconst:
