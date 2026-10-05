=================================
project_member diff
=================================

Description
=================================

基準プロジェクトと複数プロジェクトのメンバ構成の差分を出力します。メンバ情報は変更しません。
プロジェクトの指定方法と比較対象のプロパティは :doc:`sync` を参照してください。
両プロジェクトの参照権限が必要です。同期先のオーナロールは不要です。

``action`` は、構成を揃えるために必要な操作を示します。
``add`` は追加（脱退済みメンバの再登録を含む）、``update`` はロール・抜取率の更新、
``delete`` は同期先にだけいる有効なメンバの脱退です。
``delete`` は常に表示しますが、``sync`` が実行するのは ``--delete_extra_members`` 指定時だけです。

``src_`` と ``dest_`` で始まる列は、基準プロジェクトと同期先の値です。
自分自身や組織外のユーザの差分も表示します。
``skip_reason`` に理由がある行は ``sync`` で変更しません。
差分がなければCSVはヘッダ行のみ、JSONは空配列を出力します。

Examples
=================================

CSVで出力する
--------------------------

.. code-block::

    $ annofabcli project_member diff --src_project_id prj1 --dest_project_id prj2 prj3 --format csv --output diff.csv

.. csv-table:: CSVの出力例
   :file: diff/out.csv
   :header-rows: 1

JSONで出力する
--------------------------

.. code-block::

    $ annofabcli project_member diff --src_project_id prj1 --dest_project_id prj2 --format pretty_json --output diff.json

.. code-block:: json

    [
      {
        "src_project_id": "prj1",
        "dest_project_id": "prj2",
        "user_id": "user1",
        "action": "update",
        "skip_reason": "",
        "src_member_role": "worker",
        "src_sampling_inspection_rate": 10,
        "src_sampling_acceptance_rate": null,
        "dest_member_role": "accepter",
        "dest_sampling_inspection_rate": 20,
        "dest_sampling_acceptance_rate": null
      }
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.diff_project_members.add_parser
   :prog: annofabcli project_member diff
   :nosubcommands:
   :nodefaultconst:
