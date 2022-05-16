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
アノテーションZIPのフォーマットについては https://annofab.com/docs/api/#section/Simple-Annotation-ZIP を参照してください。

.. code-block::

    $ annofabcli annotation download --project_id prj1 --output annotation.zip

作成したアノテーションは、03:00(JST)頃にアノテーションZIPに反映されます。
現在のアノテーションの状態をアノテーションZIPに反映させたい場合は、``--latest`` を指定してください。
アノテーションZIPへの反映が完了したら、ダウンロードされます。
ただし、データ数に応じて数分から数十分待ちます。


.. code-block::

    $ annofabcli annotation download --project_id prj1 --output annotation.zip --latest



FullアノテーションZIPダウンロード（非推奨）
----------------------------------------------------

``--download_full_annotation`` を指定すると、FullアノテーションZIPダウンロードされます。
FullアノテーションZIPのフォーマットについては https://annofab.com/docs/api/#section/Full-Annotation-ZIP を参照してください。

ただし、``--download_full_annotation`` は非推奨です。将来、廃止される可能性があります。

.. code-block::

    $ annofabcli annotation download --project_id prj1 --output full-annotation.zip --download_full_annotation


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.download_annotation_zip.add_parser
    :prog: annofabcli annotation download
    :nosubcommands:
    :nodefaultconst:


