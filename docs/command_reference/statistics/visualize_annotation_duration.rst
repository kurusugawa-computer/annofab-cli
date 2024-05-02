==========================================
statistics visualize_annotation_duration
==========================================

Description
=================================

ラベルごとまたは属性値ごとに、区間アノテーションの長さをヒストグラムで可視化したファイルを出力します。

Examples
=================================

.. code-block::

    $ annofabcli statistics visualize_annotation_duration --project_id prj1 --output_dir out_dir/


.. code-block::

    out_dir/ 
    ├── annotation_duration_by_label.html                ラベルごとの区間アノテーションの長さをヒストグラムで可視化したHTMLファイル
    ├── annotation_duration_by_attribute.html            属性ごとの区間アノテーションの長さをヒストグラムで可視化したHTMLファイル
    │


下図は ``annotation_duration_by_label.html`` の中身です。ラベル名ごとにヒストグラムが描画されています。


.. image:: visualize_annotation_duration/img/annotation_duration_by_label.png
    :alt: annotation_duration_by_label


下図は ``annotation_duration_by_attribute.html`` の中身です。ラベル名、属性名、属性値のペアごとにヒストグラムが描画されています。

.. image:: visualize_annotation_duration/img/annotation_duration_by_attribute.png
    :alt: annotation_duration_by_attribute

集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス




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


`out_by_task <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize_annotation_count/out_by_task>`_



`labels_count.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_count/out_by_task/labels_count.html>`_

`attributes_count.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_count/out_by_task/attributes_count.html>`_



Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.visualize_annotation_duration.add_parser
   :prog: annofabcli statistics visualize_annotation_duration
   :nosubcommands:
   :nodefaultconst:
