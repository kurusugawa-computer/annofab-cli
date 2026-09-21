==========================================
annotation delete_invalid_attribute_value
==========================================

Description
=================================
ラベルに含まれていない属性値を削除します。
アノテーション自体は削除しません。

アノテーションを付与した後に、アノテーション仕様画面で「属性XをラベルAから削除する」といった変更を行うと、Annofabのアノテーションエディタ画面にエラーアイコンが表示されます。
このエラーを解消するには、アノテーションエディタ画面で対象フレームを保存する必要があります。
ただし、対象フレームが多い場合、画面上で1件ずつ保存するのは手間がかかります。
そのような場合は、このコマンドを利用することで、ラベルに含まれていない属性値を一括で削除できます。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に属性値削除対象のタスクのtask_idを指定してください。
``--task_id`` を省略すると、プロジェクト内の全タスクを対象にします。
ただし、プロジェクト内のタスク数が10,000件を超える場合は、全タスクを安全に取得できないため処理を中断します。その場合は ``--task_id`` で対象タスクを絞り込んでください。

.. code-block::

    $ annofabcli annotation delete_invalid_attribute_value --project_id prj1 --task_id file://task.txt \
    --backup backup_dir/


プロジェクト内の全タスクを対象にする
--------------------------------------------------------------------

.. code-block::

    $ annofabcli annotation delete_invalid_attribute_value --project_id prj1 --backup backup_dir/


.. note::

    ``--task_id`` を省略したときに、プロジェクト内のタスク数が10,000件を超える場合は処理を中断します。必要に応じて ``--task_id`` で対象タスクを絞り込んでください。


``--backup`` にディレクトリを指定すると、変更対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

.. note::

    間違えてアノテーション属性値を削除したときに復元できるようにするため、``--backup`` を指定することを推奨します。


.. note::

    作業中状態のタスクに含まれるアノテーションは変更できません。
    完了状態のタスクのアノテーションは、デフォルトでは変更できません。 ``--include_complete_task`` を指定すれば、完了状態のタスクに含まれるアノテーションも変更できます。ただし、``--include_complete_task`` はオーナーロールを持つユーザーでしか実行できません。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.delete_invalid_attribute_value.add_parser
    :prog: annofabcli annotation delete_invalid_attribute_value
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_
