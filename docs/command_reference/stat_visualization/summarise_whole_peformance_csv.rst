====================================================================================
stat_visualization summarise_whole_peformance_csv
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイル ``全体の生産性と品質.csv`` をプロジェクトごとにまとめます。



Examples
=================================

基本的な使い方
--------------------------

``--dir`` に ``annofabcli statistics visualize`` コマンドの出力先ディレクトリが存在するディレクトリのパスを指定してください。
``annofabcli statistics visualize`` コマンドの出力ファイルである ``全体の生産性と品質.csv`` を読み込みます。


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out/prj1_dir/
    $ annofabcli statistics visualize --project_id prj2 --output_dir out/prj2_dir/

    $ annofabcli stat_visualization summarise_whole_peformance_csv --dir out/ \
     --output プロジェクトごとの生産性と品質.csv





出力結果
=================================

.. code-block::

    $ annofabcli stat_visualization summarise_whole_peformance_csv --dir out/ \
     --output プロジェクトごとの生産性と品質.csv

`プロジェクトごとの生産性と品質.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/stat_visualization/summarise_whole_peformance_csv/プロジェクトごとの生産性と品質.csv>`_


See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_

