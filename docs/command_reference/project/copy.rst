=================================
project copy
=================================

Description
=================================
プロジェクトをコピーします。

Examples
=================================

基本的な使い方
--------------------------
``--project_id`` にコピー元プロジェクトのproject_id、``--dest_title`` にコピー先プロジェクトの名前を指定してください。
コピー元プロジェクトの以下の情報がコピーされます。

* プロジェクト設定
* プロジェクトメンバ
* アノテーション仕様

.. code-block::

    $ annofabcli project copy --project_id prj1 --dest_title prj2-title

コピー先プロジェクトのproject_idは、デフォルトではUUIDv4になります。project_idを指定する場合は、``dest_project_id`` を指定してください。

.. code-block::

    $ annofabcli project copy --project_id prj1 --dest_title prj2-title  --dest_project_id prj2

デフォルトでは、タスクや入力データなどはコピーされません。コピー対象のデータを指定する場合は、コマンドライン引数を指定してください。
指定できる値は以下の通りです。


* ``--copy_inputs`` : 入力データ
* ``--copy_tasks`` : タスク
* ``--copy_annotations`` : アノテーション
* ``--copy_webhooks`` : Webhook
* ``--copy_supplementaly_data`` : 補助情報
* ``--copy_instructions`` : 作業ガイド


.. code-block::

    $ annofabcli project copy --project_id prj1 --dest_title prj2-title  --copy_annotations

デフォルトではコピーの完了を待たずに処理が終了します。コピーがが完了するまで処理を継続する場合は、 ``--wait`` を指定してください。

.. code-block::

    $ annofabcli project copy --project_id prj1 --dest_title prj2-title  --wait

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.copy_project.add_parser
   :prog: annofabcli project copy
   :nosubcommands:
