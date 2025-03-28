==========================================
annotation merge_segmentation
==========================================

Description
=================================
複数の塗りつぶしアノテーションを1つにまとめます。
ラベルの種類を「塗りつぶし（インスタンスセグメンテーション）」から「塗りつぶしv2（セマンティックセグメンテーション）」に変更する場合などに有用です。


Examples
=================================


以下のコマンドは、複数の ``road`` ラベルの塗りつぶしアノテーションを一つにまとめます。

.. code-block::

    $ annofabcli annotation merge_segmentation --project_id prj1 --task_id task1 --label_name road



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.merge_segmentation.add_parser
    :prog: annofabcli annotation merge_segmentation
    :nosubcommands:
    :nodefaultconst:

