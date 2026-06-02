==================================================
annotation_zip visualize_annotation_count_by_label
==================================================

Description
=================================

ラベルごとのアノテーション数をヒストグラムで可視化したHTMLファイルを出力します。

アノテーション数は、ダウンロードしたアノテーションZIPから算出します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_zip visualize_annotation_count_by_label --project_id prj1 --output labels_count.html

デフォルトではタスク単位でアノテーション数を集計します。入力データ単位に集計する場合は、 ``--group_by input_data_id`` を指定してください。

``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli annotation_zip visualize_annotation_count_by_label --project_id prj1 --annotation annotation.zip --output labels_count.html

入力データごとに可視化する
--------------------------

.. code-block::

    $ annofabcli annotation_zip visualize_annotation_count_by_label --project_id prj1 --group_by input_data_id --output labels_count.html

集計結果をCSV/JSONで出力したい場合は、 :doc:`count_annotation_by_label` を使用してください。


Command line options
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.visualize_annotation_count_by_label.add_parser
   :prog: annofabcli annotation_zip visualize_annotation_count_by_label
   :nosubcommands:
