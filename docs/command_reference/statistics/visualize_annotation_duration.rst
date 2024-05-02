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




下図は `annotation_duration_by_label.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_duration/output/annotation_duration_by_label.html>`_ の中身です。ラベル名ごとにヒストグラムが描画されています。


.. image:: visualize_annotation_duration/img/annotation_duration_by_label.png
    :alt: annotation_duration_by_label.htmlの中身


下図は `annotation_duration_by_attribute.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_duration/output/annotation_duration_by_attribute.html>`_ の中身です。ラベル名、属性名、属性値のペアごとにヒストグラムが描画されています。

.. image:: visualize_annotation_duration/img/annotation_duration_by_attribute.png
    :alt: annotation_duration_by_attribute.htmlの中身

集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス

デフォルトでは、各ヒストグラムのデータの範囲やビンの幅は異なります。すべてのヒストグラムでデータの範囲とビンの幅を揃える場合は、 ``--arrange_bin_edge`` を指定します。


.. code-block::

    $ annofabcli statistics visualize_annotation_duration --project_id prj1 --output_dir out_dir/ \
    --arrange_bin_edge


.. image:: visualize_annotation_duration/img/annotation_duration_by_label__with_arrange_bin_edge.png
    :alt: annotation_duration_by_label.htmlの中身（--arrange_bin_edgeを指定）
    




Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.visualize_annotation_duration.add_parser
   :prog: annofabcli statistics visualize_annotation_duration
   :nosubcommands:
   :nodefaultconst:
