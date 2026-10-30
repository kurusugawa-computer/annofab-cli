==========================================
annotation download
==========================================

Description
=================================
アノテーションZIPをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、アノテーションZIPがダウンロードされます。
アノテーションZIPのフォーマットについては https://annofab.readme.io/docs/annotation-format を参照してください。

.. code-block::

    $ annofabcli annotation download --project_id prj1 --output annotation.zip

作成したアノテーションは、03:00(JST)頃にアノテーションZIPに反映されます。
現在のアノテーションの状態をアノテーションZIPに反映させたい場合は、``--latest`` を指定してください。
アノテーションZIPへの反映が完了したら、ダウンロードされます。
ただし、データ数に応じて数分から数十分待ちます。


.. code-block::

    $ annofabcli annotation download --project_id prj1 --output annotation.zip --latest



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.download_annotation_zip.create_parser
    :prog: annofabcli annotation download
    :nosubcommands:
    :nodefaultconst:


