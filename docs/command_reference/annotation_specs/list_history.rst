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




出力結果
=================================


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
