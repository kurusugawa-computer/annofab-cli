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
    ├── attirbutes_count.csv            属性ごとのアノテーション数が記載されたCSV
    │


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

`out_by_task <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/list_annotation_count/out_by_task>`_


入力データごとにアノテーション数を集計
----------------------------------------------


.. code-block::

    $ annofabcli statistics list_annotation_count --project_id prj1 --output_dir out_by_input_data/ \
    --group_by input_data_id

`out_by_input_data <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/list_annotation_count/out_by_input_data>`_

