=====================
project_member list
=====================

Description
=================================
プロジェクトメンバ一覧を出力します。





Examples
=================================


基本的な使い方
--------------------------

``--project_id`` に出力対象のプロジェクトのproject_idを指定してください。


.. code-block::

    $ annofabcli project_member list --project_id prj1 prj2





出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli project_member list --project_id prj1  --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/project_member/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli project_member list --project_id prj1  --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "project_id": "prj1",
            "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "user_id": "user1",
            "username": "test-user1",
            "biography": null,
            "member_status": "active",
            "member_role": "owner",
            "updated_datetime": "2020-12-30T22:56:45.493+09:00",
            "created_datetime": "2019-04-19T16:29:41.069+09:00",
            "sampling_inspection_rate": null,
            "sampling_acceptance_rate": null,
            "project_title": "test-project"
        },
      ...
    ]


user_idの一覧を出力
----------------------------------------------

.. code-block::

    $ annofabcli task list --project_id prj1 --format user_id_list --output out.txt


.. code-block::
    :caption: out.txt

    user1
    user2
    ...

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.list_users.add_parser
   :prog: annofabcli project_member list
   :nosubcommands:
   :nodefaultconst:

