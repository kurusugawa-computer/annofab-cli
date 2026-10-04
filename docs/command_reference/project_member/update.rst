=================================
project_member update
=================================

Description
=================================

既存のプロジェクトメンバのロール、抜取検査率、抜取受入率をCSVまたはJSONで更新します。
自分自身と、プロジェクトに所属していないユーザ（脱退済みを含む）は更新しません。
複数ユーザに同じロールを設定する場合は :doc:`update_role` を使用してください。

旧 ``project_member change`` の代わりに、このコマンドまたは ``update_role`` を使用してください。

Examples
=================================

JSONで更新する
---------------------------------

``--project_id`` に対象プロジェクト、``--json`` に更新情報の配列を指定します。
ユーザごとに ``user_id`` と更新するプロパティを記載してください。

* ``member_role``: ロール。指定できる値は :doc:`update_role` を参照してください。
* ``sampling_inspection_rate``: 抜取検査率（0～100の整数）
* ``sampling_acceptance_rate``: 抜取受入率（0～100の整数）

省略したキーの値は維持します。抜取率に ``null`` を指定すると設定を解除します。
``member_role`` に ``null`` は指定できません。

.. code-block::

    $ annofabcli project_member update --project_id prj1 \
      --json '[{"user_id":"user1","member_role":"worker"},{"user_id":"user2","sampling_inspection_rate":null,"sampling_acceptance_rate":20}]'

JSONファイルを指定する場合は ``--json file://members.json`` を使用してください。

CSVで更新する
---------------------------------

ヘッダ行あり、カンマ区切りのCSVを ``--csv`` に指定します。
各列はJSONのキーに対応します。必須列は ``user_id`` で、他の列は省略できます。
空欄の値は維持します。抜取率の設定解除にはJSONを使用してください。
同じ ``user_id`` を複数行に記載することはできません。

.. code-block::
    :caption: members.csv

    user_id,member_role,sampling_inspection_rate,sampling_acceptance_rate
    user1,worker,,
    user2,,10,20

.. code-block::

    $ annofabcli project_member update --project_id prj1 --csv members.csv

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.update_project_members.add_parser
   :prog: annofabcli project_member update
   :nosubcommands:
   :nodefaultconst:
