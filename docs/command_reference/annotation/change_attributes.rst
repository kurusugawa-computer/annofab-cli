==========================================
annotation change_attributes
==========================================

Description
=================================
アノテーションの属性を一括で変更します。
ただし、作業中状態のタスクのアノテーションは、属性を変更できません。







Examples
=================================


基本的な使い方
--------------------------

``--task_id`` にアノテーション変更対象のタスクのtask_idを指定してください。

``--annotation_query`` には、変更対象のアノテーションを検索するする条件をJSON形式で指定してください。フォーマットは https://annofab.com/docs/api/#section/AnnotationQuery とほとんど同じです。
さらに追加で ``label_name_en`` , ``additional_data_definition_name_en`` , ``choice_name_en`` キーも指定できます。``label_id`` または ``label_name_en`` のいずれかは必ず指定してください。
``--annotation_query`` のサンプルは、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。


``--attributes`` に、変更後の属性を指定してください。フォーマットは ``--annotation_query`` の ``attributes`` キーの値と同じです。

以下のコマンドは、ラベル名（英語）の値が"car"であるアノテーションに対して、属性名(英語)が"occluded"である値をfalse（"occluded"チェックボックスをOFF）に変更します。

.. code-block::

    $ annofabcli annotation change_attributes --project_id prj1 --task_id file://task.txt \ 
    --annotation_query '{"label_name_en": "car"}' \
    --attributes '[{"additional_data_definition_name_en": "occluded", "flag": false}]' \
    --backup backup_dir/

``--backup`` にディレクトリを指定すると、変更対象のタスクのアノテーション情報を、バックアップとしてディレクトリに保存します。
アノテーション情報の復元は、 `annofabcli annotation restore <../annotation/restore.html>`_ コマンドで実現できます。


.. note::

    間違えてアノテーションを変更したときに復元できるようにするため、``--backup`` を指定することを推奨します。

デフォルトでは完了状態のタスクのアノテーションは変更できません。完了状態のタスクのアノテーションも変更する場合は、``--force`` を指定してください。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.change_annotation_attributes.add_parser
    :prog: annofabcli annotation change_attributes
    :nosubcommands:


See also
=================================
*  `annofabcli annotation restore <../annotation/restore.html>`_

