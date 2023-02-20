==========================================
annotation change_properties
==========================================

Description
=================================

アノテーションのプロパティを一括で変更します。ただし、作業中状態のタスクのアノテーションのプロパティは変更できません。


Examples
=================================


基本的な使い方
--------------------------

``--properties`` に変更したいプロパティの名前と値をJSON形式で指定してください。
変更可能なプロパティは以下の通りです。各プロパティの詳細は `putAnnotation API <https://annofab.com/docs/api/#operation/putAnnotation>`_ のリクエストボディを参照してください。

* ``is_protected`` ：trueの場合、アノテーションをアノテーションエディタ上での削除から保護できます。 


.. code-block::

    $ annofabcli annotation change_properties --project_id prj1 --task_id task1 task2 \ 
    --properties '{"is_protected":true}' \


変更対象のアノテーションを絞り込む場合は、``--annotation_query`` を指定してください。
``--annotation_query`` の詳細な使い方は、`Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。

.. code-block::

    $ annofabcli annotation change_properties --project_id prj1 --task_id task1 task2 \ 
    --properties '{"is_protected":true}' \
    --annotation_query '{"label": "car", "attributes":{"occluded": true}}' 



デフォルトでは「担当者が自分自身でない AND 担当者が割り当てられたことがある」タスクは、アノテーションプロパティの変更をスキップします。
``--force`` を指定すると、担当者を一時的に自分自身に変更して、アノテーションのプロパティを変更できます。


.. code-block::

    $ annofabcli annotation change_properties --project_id prj1 --task_id task1 task2 \ 
    --properties '{"is_protected":true}' --force \



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.change_annotation_properties.add_parser
    :prog: annofabcli annotation change_properties
    :nosubcommands:
    :nodefaultconst:


