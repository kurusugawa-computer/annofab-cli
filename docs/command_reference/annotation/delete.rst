==========================================
annotation delete
==========================================

Description
=================================
タスク配下のアノテーションを削除します。
ただし、完了状態のタスクのアノテーションは削除できません。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に削除対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \
    --backup backup


``--backup`` にディレクトリを指定すると、削除対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションを削除したときに復元できるようにするため、``--backup`` を指定することを推奨します。



削除するアノテーションを絞り込む場合は、``--annotation_query`` を指定してください。
``--annotation_query`` のサンプルは、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。

以下のコマンドは、ラベル名（英語）の値が"car"で、属性名(英語)が"occluded"である値をfalse（"occluded"チェックボックスをOFF）であるアノテーションを削除します。


.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \ 
    --annotation_query '{"label": "car", "attributes":{"occluded": false}}' \
    --backup backup_dir/


デフォルトでは完了状態のタスクのアノテーションを削除できません。完了状態のタスクのアノテーションも変更する場合は、``--force`` を指定してください。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.delete_annotation.add_parser
    :prog: annofabcli annotation delete
    :nosubcommands:
    :nodefaultconst:

See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_

