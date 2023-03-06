=====================
organization list
=====================

Description
=================================
自分が所属している組織の一覧を出力します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli organization list



出力結果
=================================


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli organization list --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "organization_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "name": "org1",
            "email": "foo@example.com",
            "price_plan": "free",
            "summary": {},
            "created_datetime": "2019-06-13T18:17:11.034+09:00",
            "updated_datetime": "2019-06-13T18:17:11.034+09:00",
            "my_role": "administrator",
            "my_status": "active"
        }
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization.list_organization.add_parser
   :prog: annofabcli organization list
   :nosubcommands:
   :nodefaultconst:
