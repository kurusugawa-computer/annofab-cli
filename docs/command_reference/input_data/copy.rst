=================================
input_data copy
=================================

Description
=================================
入力データと関連する補助情報を別プロジェクトにコピーします。

プライベートストレージを参照している入力データをコピーできます。Annofabストレージを参照している入力データはコピーできません。またコピー先プロジェクトは、プライベートストレージが利用可能である必要があります。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、プロジェクト ``prj1`` のすべての入力データとそれに紐づく補助情報を、プロジェクト ``prj2`` プロジェクトにコピーします。

.. code-block::

    $ annofabcli input_data copy --src_project_id prj1 --dest_project_id prj2

``--input_data_id`` でコピー対象の入力データを指定できます。


.. code-block::

    $ annofabcli input_data copy --src_project_id prj1 --input_data_id i1 i2 \
    --dest_project_id prj2



Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.copy_input_data.add_parser
   :prog: annofabcli input_data copy
   :nosubcommands:
   :nodefaultconst:

