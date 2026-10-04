==================================================
project_member
==================================================

Description
=================================
プロジェクトメンバ関係のコマンドです。

旧 ``project_member put`` は削除しました。メンバの追加には :doc:`invite`、
既存メンバのロール・抜取率の更新には :doc:`update`、脱退には :doc:`delete` を使用してください。
ユーザごとに異なるロールで追加する場合は、ロール別に ``invite`` を実行してください。

``update`` のCSVでは、抜取率の空欄や列の省略は現在の値を維持します。
旧 ``put`` と同様に設定を解除するには、JSONで抜取率に ``null`` を指定してください。
旧 ``put --delete`` に相当する一括同期機能はありません。
:doc:`list` で現在のメンバを取得し、CSVにないユーザを ``delete`` で指定してください。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   copy
   delete
   invite
   list
   update
   update_role

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.subcommand_project_member.add_parser
   :prog: annofabcli project_member
   :nosubcommands:
