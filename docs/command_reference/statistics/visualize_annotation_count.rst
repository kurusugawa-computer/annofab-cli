==========================================
statistics visualize_annotation_count
==========================================

Description
=================================

各ラベル、各属性値のアノテーション数をヒストグラムで可視化したファイルを出力します。



Examples
=================================

基本的な使い方
--------------------------

アノテーションzipをダウンロードして、アノテーション数が記載されたCSVファイルを出力します。


.. code-block::

    $ annofabcli statistics visualize_annotation_count --project_id prj1 --output_dir out_dir/


.. code-block::

    out_dir/ 
    ├── labels_count.html                ラベルごとのアノテーション数をヒストグラムで可視化したHTMLファイル
    ├── attributes_count.html            属性ごとのアノテーション数をヒストグラムで可視化したHTMLファイル
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

.. code-block::

    $ annofabcli statistics visualize_annotation_count --project_id prj1 --output_dir out_by_task/ \
    --group_by task_id


.. code-block::

    out_by_task/
    ├── labels_count.html
    ├── attributes_count.html


.. image:: visualize_annotation_count/img/labels_count.png


`out_by_task <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/visualize_annotation_count/out_by_task>`_



`labels_count.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_count/out_by_task/labels_count.html>`_

`attributes_count.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_count/out_by_task/attributes_count.html>`_



Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.visualize_annotation_count.add_parser
   :prog: annofabcli statistics visualize_annotation_count
   :nosubcommands:
   :nodefaultconst:
