==========================================
organization_member list
==========================================

Description
=================================
組織メンバ一覧を出力します。





Examples
=================================


基本的な使い方
--------------------------

``--organization`` に組織名を指定してください。


.. code-block::

    $ annofabcli organization_member list --organization org1 org2




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli organization_member list --project_id prj1  --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/organization_member/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli organization_member list --organization org1  --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "organization_id": "org1",
            "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "user_id": "user1",
            "username": "username1",
            "biography": null,
            "role": "owner",
            "status": "active",
            "updated_datetime": "2018-09-13T18:06:46.598+09:00",
            "created_datetime": "2018-06-20T10:13:43.798+09:00",
            "organization_name": "orgname1"
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.list_organization_member.add_parser
   :prog: annofabcli organization_member list
   :nosubcommands:
   :nodefaultconst:
