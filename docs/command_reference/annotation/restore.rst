

==========================================
annotation restore
==========================================

Description
=================================
アノテーション情報をリストアします。
ただし、作業中状態のタスクに対してはアノテーション情報をリストアできません。
オーナーロールまたはチェッカーロールを持つユーザーが実行できます。


Examples
=================================


基本的な使い方
--------------------------

``--annotation`` に、以下のいずれかのディレクトリパスを指定してください。

* `annofabcli annotation dump <../annotation/dump.html>`_ コマンドの出力先ディレクトリ
* `annofabcli annotation delete <../annotation/delete.html>`_ コマンドのバックアップ先ディレクトリ
* `annofabcli annotation change_attributes <../annotation/change_attributes.html>`_ コマンドのバックアップ先ディレクトリ

.. code-block::

    $ annofabcli annotation dump --project_id prj1 --task_id file://task.txt --output_dir backup-dir/

    $ annofabcli annotation restore --project_id prj1 --annotation backup-dir/


リストア対象のタスクを指定する場合は、``--task_id`` にリストア対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation restore --project_id prj1 --annotation backup-dir/ \
    --task_id t1 t2



オーナーロールでは、タスクの担当者や状態を変更せずにアノテーションをリストアできます。
チェッカーロールで自身が担当者ではないタスクにリストアするには、 ``--change_operator_to_me`` を指定してください。担当者を一時的に自分自身に変更してアノテーションをリストアします。オーナーロールで指定しても効果はありません。

.. code-block::

    $ annofabcli annotation restore --project_id prj1 --annotation backup-dir/ \
    --change_operator_to_me


デフォルトでは、休憩中状態のタスクはアノテーションのリストアをスキップします。
休憩中状態のタスクにもリストアする場合は、 ``--include_break_task`` を指定してください。

完了状態のタスクにリストアするには、オーナーロールで ``--include_complete_task`` を指定してください。

デフォルトでは、保留中状態のタスクはアノテーションのリストアをスキップします。
保留中状態のタスクにもリストアする場合は、 ``--include_on_hold_task`` を指定してください。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.restore_annotation.add_parser
    :prog: annofabcli annotation restore
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation dump <../annotation/dump.html>`_
