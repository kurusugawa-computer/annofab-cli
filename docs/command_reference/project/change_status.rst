=================================
project change_status
=================================

Description
=================================
プロジェクトのステータスを変更します。


Examples
=================================

基本的な使い方
--------------------------
``--status`` に変更後のステータスを指定してください。指定できる値は以下の通りです。

* ``active`` : 進行中
* ``suspended`` : 停止中


以下のコマンドは、プロジェクトprj1, prj2のステータスを「進行中」にします。

.. code-block::

    $ annofabcli project change_status --project_id prj1 prj2 --status active


デフォルトでは、作業中タスクが残っている状態で、プロジェクトのステータスを「停止中」に変更できません。
作業中タスクが残っている状態で、プロジェクトのステータスを「停止中」に変更する場合は、``--force`` を指定してください。

.. code-block::

    $ annofabcli project change_status --project_id prj1 prj2 --status suspended --force

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.change_project_status.add_parser
   :prog: annofabcli project change_status
   :nosubcommands:
   :nodefaultconst:
