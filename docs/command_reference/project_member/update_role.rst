=================================
project_member update_role
=================================

Description
=================================

複数のプロジェクトメンバに同じロールを設定します。抜取率は維持します。
自分自身と、プロジェクトに所属していないユーザ（脱退済みを含む）は更新しません。
ユーザごとに異なるロールや抜取率を設定する場合は :doc:`update` を使用してください。

Examples
=================================

ユーザを指定する
---------------------------------

``--user_id`` に対象ユーザ、``--role`` に共通して設定するロールを指定します。

* ``worker``: アノテータ
* ``accepter``: チェッカー
* ``training_data_user``: アノテーションユーザ
* ``owner``: プロジェクトオーナ

.. code-block::

    $ annofabcli project_member update_role --project_id prj1 --user_id user1 user2 --role worker

ユーザIDの一覧ファイルを指定する場合は ``--user_id file://users.txt`` を使用してください。

全メンバを指定する
---------------------------------

``--all_users`` を指定すると、自分以外のすべての有効なプロジェクトメンバを対象にします。

.. code-block::

    $ annofabcli project_member update_role --project_id prj1 --all_users --role worker

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.update_project_member_roles.add_parser
   :prog: annofabcli project_member update_role
   :nosubcommands:
   :nodefaultconst:
