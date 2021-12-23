=================================
project update_annotation_zip
=================================

Description
=================================
アノテーションzipを更新（最新化）します。

Examples
=================================

基本的な使い方
--------------------------
``--project_id`` にアノテーションzipを更新するプロジェクトを複数指定してください。

.. code-block::

    $ annofabcli project update_annotation_zip --project_id prj1 prj2

デフォルトでは、アノテーションzipを更新する必要がない場合は、更新しません。常にアノテーションzipを更新する場合は、 ``--force`` を指定してください。

.. code-block::

    $ annofabcli project update_annotation_zip --project_id prj1 prj2 --force

すべてのプロジェクトの更新が完了するまで待つ場合は、``--wait`` を指定してください。

.. code-block::

    $ annofabcli project update_annotation_zip --project_id prj1 prj2 --wait


.. note::

    以下の条件を1つ以上満たす場合は、アノテーションzipを更新する必要があります。

    * タスクの最終更新日時が、アノテーションzipの最終更新日時より新しい
    * アノテーション仕様の最終更新日時が、アノテーションzipの最終更新日時より新しい



並列処理
----------------------------------------------
デフォルトの並列数は、指定したproject_idの個数です。並列数を指定する場合は、``--parallelism`` を指定してください。

.. code-block::

    $  annofabcli project change_status --project_id file://project_id.txt \
    --parallelism 4 

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.update_annotation_zip.add_parser
   :prog: annofabcli project update_annotation_zip
   :nosubcommands:
   :nodefaultconst:
