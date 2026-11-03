=================================
project change_status
=================================

Description
=================================
プロジェクトのステータスを変更します。

変更先の状態に遷移できない場合（HTTP 409）は、そのプロジェクトをスキップします。
並列実行では、重複するプロジェクトIDは1回だけ処理します。
一部の処理に失敗してもほかのプロジェクトの処理完了を待ち、成功・スキップ・失敗の件数をログに出力します。
HTTP 409以外のエラーによる失敗があった場合は、非0の終了コードで終了します。


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
作業中タスクが残っている状態で、プロジェクトのステータスを「停止中」に変更する場合は、``--suspend_with_working_tasks`` を指定してください。

.. code-block::

    $ annofabcli project change_status --project_id prj1 prj2 --status suspended --suspend_with_working_tasks

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.change_project_status.create_parser
   :prog: annofabcli project change_status
   :nosubcommands:
   :nodefaultconst:
