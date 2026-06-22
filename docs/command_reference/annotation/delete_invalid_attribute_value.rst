==========================================
annotation delete_invalid_attribute_value
==========================================

Description
=================================
ラベルに含まれていない属性値を削除します。
アノテーション自体は削除しません。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に属性値削除対象のタスクのtask_idを指定してください。

このコマンドは、現在のアノテーション仕様でラベルごとに定義されている属性IDと、アノテーションに付与されている属性値の属性IDを比較します。
アノテーションのラベルに含まれていない属性値だけを削除します。

.. code-block::

    $ annofabcli annotation delete_invalid_attribute_value --project_id prj1 --task_id file://task.txt \
    --backup backup_dir/


``--backup`` にディレクトリを指定すると、変更対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。

.. note::

    間違えてアノテーション属性値を削除したときに復元できるようにするため、``--backup`` を指定することを推奨します。


.. note::

    作業中状態のタスクに含まれるアノテーションは変更できません。
    完了状態のタスクのアノテーションは、デフォルトでは変更できません。 ``--include_complete_task`` を指定すれば、完了状態のタスクに含まれるアノテーションも変更できます。


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
