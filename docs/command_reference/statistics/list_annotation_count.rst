==========================================
statistics list_annotation_count
==========================================

Description
=================================

各ラベルまたは各属性値のアノテーション数を出力します。



Examples
=================================

基本的な使い方
--------------------------

アノテーションzipをダウンロードして、アノテーション数が記載されたCSVファイルを出力します。


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_dir/


.. code-block::

    out_dir/ 
    ├── labels_count.csv                ラベルごとのアノテーション数が記載されたCSV
    ├── attributes_count.csv            属性ごとのアノテーション数が記載されたCSV
    │

集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス


デフォルトではタスクごとにアノテーション数を集計します。入力データごとに集計する場合は、 ``--group_by input_data_id`` を指定してください。

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_dir/ \
    --group_by input_data_id


``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_dir/ \
    --annotation annotation.zip



出力結果
=================================

タスクごとにアノテーション数を集計
----------------------------------------------

.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_by_task/ \
    --group_by task_id

`out_by_task <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/list_annotation_count/out_by_task>`_


.. code-block::

    out_by_task/
    ├── labels_count.csv
    ├── attributes_count.csv



.. csv-table:: labels_count.csv
   :header: task_id,task_status,task_phase,task_phase_stage,input_data_count,Cat,...

    task1,break,annotation,1,5,20,...
    task2,complete,acceptance,1,5,12,...



.. csv-table:: attributes_count.csv
    :header-rows: 3
    
    ,,,,,Cat,Cat,...
    ,,,,,occluded,occluded,...
    task_id,task_status,task_phase,task_phase_stage,input_data_count,True,False,...
    task1,break,acceptance,1,5,2,0,...
    task2,complete,acceptance,1,5,2,0,...





入力データごとにアノテーション数を集計
----------------------------------------------


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_by_input_data/ \
    --group_by input_data_id

`out_by_input_data <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/list_annotation_count/out_by_input_data>`_


.. code-block::

    out_by_input_data/
    ├── labels_count.csv
    ├── attributes_count.csv



.. csv-table:: labels_count.csv
   :header: input_data_id,input_data_name,task_id,task_status,task_phase,task_phase_stage,label_Cat,...

    input1,input1,task1,break,acceptance,1,12
    input2,input2,task2,complete,acceptance,1,12




.. csv-table:: attributes_count.csv
    :header-rows: 3

    ,,,,,,Cat,Cat,...
    ,,,,,,occluded,occluded,...
    input_data_id,input_data_name,task_id,task_status,task_phase,task_phase_stage,True,False,...
    input1,input1,task1,break,acceptance,1,10,5,...
    input2,input2,task2,complete,acceptance,1,10,5,...

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_annotation_count.add_parser
   :prog: annofabcli statistics list_annotation_count
   :nosubcommands:
   :nodefaultconst:
