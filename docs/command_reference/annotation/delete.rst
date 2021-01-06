==========================================
annotation delete
==========================================

Description
=================================
タスク配下のアノテーションを削除します。
ただし、作業中または完了状態のタスクのアノテーションは削除できません。




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



削除するアノテーションを絞り込む場合は、``--annotation_query`` を指定してください。フォーマットは https://annofab.com/docs/api/#section/AnnotationQuery とほとんど同じです。

以下のコマンドは、ラベル名（英語）の値が"car"で、属性名(英語)が"occluded"である値をfalse（"occluded"チェックボックスをOFF）であるアノテーションを削除します。


.. code-block::

    $ annofabcli annotation delete --project_id prj1 --task_id file://task.txt \ 
    --annotation_query '{"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": false}]}' \
    --backup backup_dir/



See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_

