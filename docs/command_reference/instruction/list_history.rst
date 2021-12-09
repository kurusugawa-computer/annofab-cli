==========================================
instruction list_history
==========================================

Description
=================================
作業ガイドの変更履歴一覧を出力します。




Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli instruction list_history --project_id prj1 




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli instruction list_history --project_id prj1  --format csv --output out.csv


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli instruction list_history --project_id prj1  --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "history_id": "59de00ca-e3fb-4436-88bb-2435c8ce5058",
            "account_id": "account1",
            "updated_datetime": "2019-04-23T20:44:37.089+09:00",
            "user_id": "user1",
            "username": "username1"
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.instruction.list_instruction_history.add_parser
   :prog: annofabcli instruction list_history
   :nosubcommands:
   :nodefaultconst:
