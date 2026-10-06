==========================================
statistics list_worktime
==========================================

Description
=================================

.. warning::

   このコマンドは非推奨です。
   代わりに `annofabcli task_history_event summarize_worktime_by_user_and_date <../task_history_event/summarize_worktime_by_user_and_date.html>`_ を使用してください。

タスク履歴イベントから、日ごとユーザーごとの作業時間を集計します。
使い方と出力例は移行先のコマンドを参照してください。
従来の引数で実行でき、実行時には非推奨警告を出力します。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_worktime.add_parser
   :prog: annofabcli statistics list_worktime
   :nosubcommands:
   :nodefaultconst:
