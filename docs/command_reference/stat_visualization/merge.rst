==========================================
stat_visualization merge
==========================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力結果をマージします。





Examples
=================================

基本的な使い方
--------------------------

``--dir`` に ``annofabcli statistics visualize`` コマンドの出力先ディレクトリのパスを複数指定してください。



.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/
    $ annofabcli statistics visualize --project_id prj2 --output_dir prj2_dir/

    $ annofabcli stat_visualization merge --dir prj1_dir/ prj2_dir/ --output_dir merge_dir/




ディレクトリ一覧をファイルで指定する
----------------------------------------------

``--dir`` は、改行区切りのディレクトリ一覧を ``file://`` で指定することもできます。
ファイルには2件以上のパスを記載してください。相対パスはコマンド実行時のカレントディレクトリを基準に解釈します。
ファイル指定は1個だけ渡してください。直接指定する値や別のファイル指定とは併用できません。

.. code-block:: text
    :caption: directories.txt

    prj1_dir/
    prj2_dir/

.. code-block:: bash

    $ annofabcli stat_visualization merge --dir file://directories.txt --output_dir merge_dir/


出力結果
=================================


.. code-block::

    $ annofabcli stat_visualization merge --dir prj1_dir/ prj2_dir/ --output_dir merge_dir/
    


.. code-block::

    merge_dir
    ├── line-graph
    │   ├── 累積折れ線-横軸_生産量-教師付者用.html
    │   └── 累積折れ線-横軸_生産量-受入者用.html
    ├── scatter
    │   ├── 散布図-生産量あたり作業時間と品質の関係-教師付者用.html
    │   ├── 散布図-生産量あたり作業時間と累計作業時間の関係.html
    │   └── 散布図-教師付者の品質と作業量の関係.html
    ├── タスクlist.csv
    └── メンバごとの生産性と品質.csv

Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.merge_visualization_dir.create_parser
   :prog: annofabcli stat_visualization merge
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_
