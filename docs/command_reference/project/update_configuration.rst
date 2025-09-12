=================================
project update_configuration
=================================

Description
=================================
複数のプロジェクトの設定を一括で更新します。
既存の設定に対して部分的な更新を行います（設定の完全な置き換えではありません）。


Examples
=================================

単一のプロジェクトの設定を更新する場合：

.. code-block::

    $ annofabcli project update_configuration --project_id prj1 --configuration '{"max_tasks_per_member": 100}'

複数のプロジェクトの設定を一括更新する場合：

.. code-block::

    $ annofabcli project update_configuration --project_id prj1 prj2 prj3 --configuration '{"max_tasks_per_member": 100, "enable_email_notification": true}'

設定をファイルから読み込む場合：

.. code-block::

    $ annofabcli project update_configuration --project_id prj1 prj2 --configuration file://config.json

プロジェクトIDをファイルから読み込む場合：

.. code-block::

    $ annofabcli project update_configuration --project_id file://project_list.txt --configuration '{"max_tasks_per_member": 50}'


Notes
=================================

* このコマンドは既存の設定を完全に置き換えるのではなく、指定された設定項目のみを更新します
* 設定に変更がない場合、そのプロジェクトはスキップされます
* プロジェクトのオーナまたは管理者ロールを持つユーザで実行してください
* 設定の詳細については `Annofab API ドキュメント <https://annofab.com/docs/api/#operation/putProject>`_ のconfigurationフィールドを参照してください


Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.update_configuration.add_parser
   :prog: annofabcli project update_configuration
   :nosubcommands:
   :nodefaultconst:
