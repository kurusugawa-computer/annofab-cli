=================================
project_member copy
=================================

Description
=================================

プロジェクトメンバを別のプロジェクトにコピーします。



Examples
=================================

基本的な使い方
--------------------------
プロジェクトメンバのコピー元プロジェクトのproject_id、コピー先プロジェクトのproject_idを指定してください。


以下のコマンドは、プロジェクトprj1のプロジェクトメンバを、プロジェクトprj2にコピーします。

.. code-block::

    $ annofabcli project_member copy prj1 prj2

コピー先プロジェクトにしかいないプロジェクトメンバを削除する場合（コピー元プロジェクトとコピー先プロジェクトのプロジェクトメンバを同期させる）は、``--delete_dest`` を指定してください。

.. code-block::

    $ annofabcli project_member copy prj1 prj2 --delete_dest

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project_member.copy_project_members.add_parser
   :prog: annofabcli project_member copy
   :nosubcommands:
   :nodefaultconst:
