==========================================
annotation list_count
==========================================

Description
=================================
task_idまたはinput_data_idで集約したアノテーションの個数を、CSV形式で出力します。






Examples
=================================


基本的な使い方
--------------------------
``--annotation_query`` に、集計対象のアノテーションを検索するする条件をJSON形式で指定してください。
``--annotation_query`` のサンプルは、 `Command line options <../../user_guide/command_line_options.html#annotation-query-aq>`_ を参照してください。



以下のコマンドは、ラベル名（英語）が"car"であるアノテーションの個数をタスクごとに出力します。

.. code-block::

    $ annofabcli annotation list_count --project_id prj1 \
    --annotation_query '{"label": "car"}' --output out_by_task.csv




.. csv-table:: out_by_task.csv
   :header: task_id,annotation_count


    task1,1
    task2,2




デフォルトではタスクごとに集計します。入力データごとに出力する場合は、``--group_by input_data_id`` を指定しでください。

.. code-block::

    $ annofabcli annotation list_count --project_id prj1 \
    --annotation_query '{"label": "car"}' --group_by input_data_id --output out_by_input_data.csv


.. csv-table:: out_by_input_data.csv
   :header: task_id,input_data_id,annotation_count

    task1,input1,1
    task1,input2,2
    task2,input3,3
    task2,input4,4


``--task_id`` で集計対象タスクを絞り込むこともできます。

.. code-block::

    $ annofabcli annotation list_count --project_id prj1 \
    --annotation_query '{"label": "car"}'  --task_id file://task.txt



.. note::

    ``--annotation_query`` にマッチするアノテーションの一覧から、アノテーションの個数を算出しいています。
    したがって、 ``annotation_count`` 列の値は必ず0より大きいです。
    

.. warning::

    WebAPIの都合上、集計対象のアノテーションは10,000個までしか検索できません。
    10,000件以上のアノテーションを集計する場合は、 `annofabcli statistics list_annotation_count <../statistics/list_annotation_count.html>`_ コマンドの使用を検討してください。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.list_annotation_count.add_parser
    :prog: annofabcli annotation list_count
    :nosubcommands:
    :nodefaultconst:


See also
=================================
* `annofabcli statistics list_annotation_count <../statistics/list_annotation_count.html>`_

