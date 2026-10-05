==================================================
organization_member
==================================================

Description
=================================
組織メンバ関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   delete
   invite
   list
   update_role

.. _organization_member_processing_logs:

一括処理のログ
=================================

``invite``、``delete``、``update_role`` は100件ごとに進捗を出力します。
各ユーザの処理順は ``--debug`` を指定すると確認できます。
組織ごとの処理完了時には、成功・スキップ・失敗件数を出力します。
``invite`` と ``delete`` で操作権限がない組織は、対象ユーザ全員をスキップ件数に含めます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.subcommand_organization_member.add_parser
   :prog: annofabcli organization_member
   :nosubcommands:
