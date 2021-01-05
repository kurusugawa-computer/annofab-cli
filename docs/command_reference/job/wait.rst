=================================
job wait
=================================

Description
=================================
ジョブの終了を待ちます。


Examples
=================================


基本的な使い方
--------------------------

``--job_type`` にジョブの種類を指定してください。
``job_type`` に指定できる値は `annofabcli job list <../job/list.html>`_ を参照してください。


以下のコマンドは、「アノテーションzipの更新」ジョブが終了するまで待ちます。

.. code-block::

    $ annofabcli job wait --project_id prj1  --job_type gen-annotation 


