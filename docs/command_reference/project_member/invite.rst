=================================
project_member invite
=================================

Description
=================================

複数のプロジェクトにユーザを招待します。


Examples
=================================

基本的な使い方
--------------------------

``--role`` に招待したいユーザのロールを指定してください。指定できる値は以下の通りです。

* ``worker`` : アノテータ
* ``accepter`` : チェッカー
* ``training_data_user`` : アノテーションユーザ
* ``owner`` : プロジェクトオーナ


組織配下のすべてのプロジェクトに招待する場合は、``--organization`` を指定してください。
以下のコマンドは、組織org1配下のすべてのプロジェクトにユーザuser1,user2をチェッカーロールで招待します。


.. code-block::

    $ annofabcli project_member invite --user_id user1 user2 --role accepter --organization org1


招待先のプロジェクトを指定する場合は、``--project_id`` を指定してください。

.. code-block::

    $ annofabcli project_member invite --user_id user1 user2 --role worker --project_id prj1 prj2

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.invite_project_members.add_parser
   :prog: annofabcli project_member change
   :nosubcommands:
   :nodefaultconst:
