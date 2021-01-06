=================================
job delete
=================================

Description
=================================
ジョブを削除します。


Examples
=================================


基本的な使い方
--------------------------

``--job_type`` にジョブの種類、``--job_id`` にjob_idを指定してください。

``--job_type`` に指定できる値は `annofabcli job list <../job/list.html>`_ を参照してください。
job_idは `annofabcli job list <../job/list.html>`_ コマンドで確認できます。



.. code-block::

    $ annofabcli job delete --project_id prj1  --job_type gen-annotation --job_id job1 job2


