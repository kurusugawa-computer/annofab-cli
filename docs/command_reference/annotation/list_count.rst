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
``--annotation_query`` に、集計対象のアノテーションを検索するする条件をJSON形式で指定してください。フォーマットは https://annofab.com/docs/api/#section/AnnotationQuery とほとんど同じです。
さらに追加で ``label_name_en`` , ``additional_data_definition_name_en`` , ``choice_name_en`` キーも指定できます。``label_id`` または ``label_name_en`` のいずれかは必ず指定してください。

``--annotation_query`` のサンプルを以下に記載します。

.. code-block::

    # ラベル名（英語)が"bike"のアノテーション
    {"label_name_en": "bike"}


    # ラベル名（英語)が"car"で、属性名(英語)が"occluded"の値がtrueである（チェックボックス）アノテーション
    {"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}]}


    # ラベル名（英語)が"car"で、属性名(英語)が"count"の値が"1"であるアノテーション
    {"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "count", "integer": 1}]}


    # ラベル名（英語)が"car"で、属性名(英語)が"note"の値が"test"であるアノテーション
    {"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "note", "comment": "test"}]}


    # ラベル名（英語)が"car"で、属性名(英語)が"weather"の値が"sunny"である（ラジオボタンまたはドロップダウン）アノテーション
    {"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "weather", "choice_name_en": "sunny"}]}


    # ラベル名（英語)が"car"で、属性名(英語)が"occluded"の値がtrue AND 属性名(英語)が"weather"の値が"sunny"であるアノテーション
    {"label_name_en": "car", "attributes":[{"additional_data_definition_name_en": "occluded", "flag": true}, 
     {"additional_data_definition_name_en": "occluded", "flag": true}]}



以下のコマンドは、ラベル名（英語)が"car"であるアノテーションの個数をタスクごとに出力します。

.. code-block::

    $ annofabcli annotation list_count --project_id prj1 \
    --annotation_query '{"label_name_en": "car"}' --output out_by_task.csv


.. csv-table:: out_by_task.csv
   :header: task_id,annotation_count


    task1,1
    task2,2


デフォルトではタスクごとに集計します。入力データごとに出力する場合は、``--gropu_by input_data_id`` を指定しでください。

.. code-block::

    $ annofabcli annotation list_count --project_id prj1 \
    --annotation_query '{"label_name_en": "car"}' --gropu_by input_data_id --output out_by_input_data.csv


.. csv-table:: out_by_input_data.csv
   :header: task_id,input_data_id,annotation_count

    task1,input1,1
    task1,input2,2
    task2,input3,3
    task2,input4,4


``--task_id`` で集計対象タスクを絞り込むこともできます。

.. code-block::

    $ annofabcli annotation list_count --project_id prj1 \
    --annotation_query '{"label_name_en": "car"}'  --task_id file://task.txt


.. warning::

    WebAPIの都合上、集計対象のアノテーションは10,000個までしか検索できません。
    10,000件以上のアノテーションを集計する場合は、 `annofabcli statistics list_annotation_count <../statistics/list_annotation_count.html>`_ コマンドの使用を検討してください。




See also
=================================
* `annofabcli statistics list_annotation_count <../statistics/list_annotation_count.html>`_

