==========================================
annotation merge_segmentation
==========================================

Description
=================================
複数の塗りつぶしアノテーションを1つにまとめます。
ラベルの種類を「塗りつぶし（インスタンスセグメンテーション）」から「塗りつぶしv2（セマンティックセグメンテーション）」に変更する場合などに有用です。
オーナーロールまたはチェッカーロールを持つユーザーが実行できます。


Examples
=================================


以下のコマンドは、複数の ``road`` ラベルの塗りつぶしアノテーションを1つにまとめます。

.. code-block::

    $ annofabcli annotation merge_segmentation --project_id prj1 --task_id task1 --label_name road

1つにまとめる際、最前面にある塗りつぶしアノテーションが更新され、それ以外の塗りつぶしアノテーションは削除されます。

デフォルトでは、休憩中状態のタスクはアノテーションの更新をスキップします。
休憩中状態のタスクも更新する場合は、 ``--include_break_task`` を指定してください。

完了状態のタスクを更新するには、オーナーロールで ``--include_complete_task`` を指定してください。

デフォルトでは、保留中状態のタスクはアノテーションの更新をスキップします。
保留中状態のタスクも更新する場合は、 ``--include_on_hold_task`` を指定してください。チェッカーロールで更新した場合、更新後は未着手状態になります。

オーナーロールでは、タスクの担当者や状態を変更せずにアノテーションを更新できます。
チェッカーロールで自身が担当者ではないタスクを更新するには、 ``--change_operator_to_me`` を指定してください。担当者を一時的に自分自身に変更して更新を実行します。オーナーロールで指定しても効果はありません。


.. figure:: merge_segmentation/before.png
    
    コマンドの実行前の状態。「pedestrian」ラベルの塗りつぶしアノテーションが3つあります。

    
.. figure:: merge_segmentation/after.png
    
    コマンドの実行前の状態。「pedestrian」ラベルの塗りつぶしアノテーションが1つにまとめらます。最前面にあった「bc45b4b2」アノテーションが更新され、残りは削除されます。
    





Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.merge_segmentation.add_parser
    :prog: annofabcli annotation merge_segmentation
    :nosubcommands:
    :nodefaultconst:
