==========================================
stat_visualization mask_user_info
==========================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力結果からユーザ情報をマスクします。

以下のユーザ情報をマスクします。

* user_id
* username
* biography
* account_id



Examples
=================================

基本的な使い方
--------------------------

``--dir`` に ``annofabcli statistics visualize`` コマンドの出力先ディレクトリのパスを指定してください。


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj-out/

    $ tree prj-out/
    prj-out/
    ├── タスクlist.csv
    ├── メンバごとの生産性と品質.csv
    ├── ユーザ_日付list-作業時間.csv
    ├── 教師付開始日毎の生産量と生産性.csv
    ├── 全体の生産性と品質.csv
    └── 日毎の生産量と生産性.csv

    $ annofabcli stat_visualization mask_user_info --dir prj-out/ --output_dir masked_out/


``--not_masked_user_id`` には「マスクしないユーザ」のuser_idを指定できます。
以下のコマンドは、``alice`` 以外のユーザをマスクします。

.. code-block::

    $ annofabcli stat_visualization mask_user_info --dir prj-out/ --output_dir masked_out/ \
     --not_masked_user_id alice


``--not_masked_biography`` には「マスクしないbiographyであるユーザ」のuser_idを指定できます。
以下のコマンドはbiographyが ``Japan`` 以外のユーザをマスクします。


.. code-block::

    $ annofabcli stat_visualization mask_user_info --dir prj-out/ --output_dir masked_out/ \
     --not_masked_biography Japan




出力結果
=================================


.. code-block::

    $ annofabcli stat_visualization mask_user_info --dir prj-dir/ --output_dir masked_out/ \
    --minimal

ユーザ情報が記載されている以下のファイルを出力します。ユーザ情報が記載されていないファイル( ``日毎の生産量と生産性.csv`` など)は出力しません。


.. code-block::

    masked_out
    ├── line-graph
    │   ├── 累積折れ線-横軸_アノテーション数-教師付者用.html
    │   └── 累積折れ線-横軸_アノテーション数-受入者用.html
    ├── scatter
    │   ├── 散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html
    │   ├── 散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html
    │   ├── 散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html
    │   └── 散布図-教師付者の品質と作業量の関係.html
    ├── タスクlist.csv
    └── メンバごとの生産性と品質.csv
    


Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.mask_visualization_dir.add_parser
   :prog: annofabcli stat_visualization mask_user_info
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_
