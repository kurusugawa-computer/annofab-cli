=================================
project diff
=================================

Description
=================================
プロジェクト間の以下の情報について、差分を出力します。





Examples
=================================

基本的な使い方
--------------------------
比較したいプロジェクトのproject_idを指定してください。

以下のコマンドは、プロジェクトprj1とprj2の差分を出力します。差分がない場合、標準出力は空です。

.. code-block::

    $ annofabcli project diff  prj1 prj2


特定の項目のみ差分を出力する場合は、``--target`` を指定してください。指定できる値は以下の通りです。

* ``annotation_labels`` : アノテーション仕様のラベル情報
* ``inspection_phrases`` : 定型指摘
* ``members`` : プロジェクトメンバ
* ``settings`` : プロジェクト設定


.. code-block::

    $ annofabcli project diff prj1 prj2 --target annotation_labels


出力結果
=================================

プロジェクト間の差分は、以下のように出力されます。


.. code-block::

    === prj1_title1(prj1) と prj1_title2(prj2) の差分を表示
    === プロジェクトメンバの差分 ===
    プロジェクトメンバは同一
    === プロジェクト設定の差分 ===
    プロジェクト設定は同一
    === 定型指摘の差分 ===
    定型指摘は同一
    === アノテーションラベル情報の差分 ===
    ラベル名(en): car は差分あり
    [('change', 'color.red', (4, 0)),
    ('change', 'color.green', (251, 255)),
    ('change', 'color.blue', (171, 204))]
    ラベル名(en): bike は同一


``dict`` 型の差分は、`dictdiffer <https://dictdiffer.readthedocs.io/en/latest/>`_ のフォーマットで出力されます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.diff_projects.add_parser
   :prog: annofabcli project diff
   :nosubcommands:
   :nodefaultconst: