=================================
project_member delete
=================================

Description
=================================

複数のプロジェクトからユーザを脱退させます。


Examples
=================================

基本的な使い方
--------------------------
組織配下のすべてのプロジェクトからプロジェクトメンバを脱退させる場合は、``--organization`` を指定してください。
以下のコマンドは、組織org1配下のすべてのプロジェクトから、ユーザuser1, user2を脱退させます。


.. code-block::

    $ annofabcli project_member delete --user_id user1 user2  --organization org1


脱退させるプロジェクトを指定する場合は、``--project_id`` を指定してください。

.. code-block::

    $ annofabcli project_member delete --user_id user1 user2  --project_id prj1 prj2

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.drop_project_members.add_parser
   :prog: annofabcli project_member delete
   :nosubcommands:
   :nodefaultconst:

