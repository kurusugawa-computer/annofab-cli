==============================================================
annotation_zip visualize_annotation_count_by_attribute_value
==============================================================

Description
=================================

属性値ごとのアノテーション数をヒストグラムで可視化したHTMLファイルを出力します。

アノテーション数は、ダウンロードしたアノテーションZIPから算出します。

集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_zip visualize_annotation_count_by_attribute_value --project_id prj1 --output attributes_count.html

デフォルトではタスク単位でアノテーション数を集計します。入力データ単位に集計する場合は、 ``--group_by input_data_id`` を指定してください。

``--annotation`` にアノテーションzipまたはzipを展開したディレクトリを指定できます。

.. code-block::

    $ annofabcli annotation_zip visualize_annotation_count_by_attribute_value --project_id prj1 --annotation annotation.zip --output attributes_count.html

入力データごとに可視化する
--------------------------

.. code-block::

    $ annofabcli annotation_zip visualize_annotation_count_by_attribute_value --project_id prj1 --group_by input_data_id --output attributes_count.html

集計結果をCSV/JSONで出力したい場合は、 :doc:`count_annotation_by_attribute_value` を使用してください。


Command line options
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.visualize_annotation_count_by_attribute_value.add_parser
   :prog: annofabcli annotation_zip visualize_annotation_count_by_attribute_value
   :nosubcommands:
