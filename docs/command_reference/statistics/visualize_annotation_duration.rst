==========================================
statistics visualize_annotation_duration
==========================================

.. deprecated:: next

    :doc:`../annotation_zip/visualize_annotation_duration_by_label` または
    :doc:`../annotation_zip/visualize_annotation_duration_by_attribute_value` を使用してください。
    このコマンドは2027-01-01以降の最初のリリースで廃止予定です。
    新コマンドは ``--project_id`` が必須で、 ``--output_dir`` の代わりに
    ``--output`` でHTMLファイルを指定します。両方のグラフが必要な場合は2コマンドを実行してください。
    旧コマンドは廃止まで従来の引数・出力を維持します。

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


.. image:: ../annotation_zip/visualize_annotation_duration_by_label/img/annotation_duration_by_label.png
    :alt: annotation_duration_by_label.htmlの中身


下図は `annotation_duration_by_attribute.html <https://kurusugawa-computer.github.io/annofab-cli/command_reference/statistics/visualize_annotation_duration/output/annotation_duration_by_attribute.html>`_ の中身です。ラベル名、属性名、属性値のペアごとにヒストグラムが描画されています。

.. image:: ../annotation_zip/visualize_annotation_duration_by_label/img/annotation_duration_by_attribute.png
    :alt: annotation_duration_by_attribute.htmlの中身

集計対象の属性の種類は以下の通りです。

* ドロップダウン
* ラジオボタン
* チェックボックス



デフォルトでは、動画の長さは「秒」単位で表示されます。「分」単位で表示する場合は、 ``--time_unit minute`` を指定してください。


.. code-block::

    $ annofabcli statistics visualize_annotation_duration --project_id prj1 --output_dir out_dir2/ \
    --time_unit minute


.. image:: ../annotation_zip/visualize_annotation_duration_by_label/img/annotation_duration_by_label__with_minute.png
    :alt: out_dir2/annotation_duration_by_label.htmlの中身



``--bin_width`` を指定するとビンの幅を「秒」単位で指定できます。以下のコマンドはビンの幅を15秒（0.25分）に指定しています。


.. code-block::

    $ annofabcli statistics visualize_annotation_duration --project_id prj1 --output_dir out_dir3/ \
    --time_unit minute --bin_width 15


.. image:: ../annotation_zip/visualize_annotation_duration_by_label/img/annotation_duration_by_label__with_bin_width.png
    :alt: out_dir3/annotation_duration_by_label.htmlの中身




デフォルトでは、各ヒストグラムのデータの範囲やビンの幅は異なります。すべてのヒストグラムでデータの範囲とビンの幅を揃える場合は、 ``--arrange_bin_edge`` を指定します。


.. code-block::

    $ annofabcli statistics visualize_annotation_duration --project_id prj1 --output_dir out_dir4/ \
    --arrange_bin_edge


.. image:: ../annotation_zip/visualize_annotation_duration_by_label/img/annotation_duration_by_label__with_arrange_bin_edge.png
    :alt: out_dir4/annotation_duration_by_label.htmlの中身
    





Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.visualize_annotation_duration.add_parser
   :prog: annofabcli statistics visualize_annotation_duration
   :nosubcommands:
   :nodefaultconst:
