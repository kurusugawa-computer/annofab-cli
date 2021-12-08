=================================
instruction download
=================================

Description
=================================
作業ガイドのHTMLファイルをダウンロードします。



Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli instruction download --project_id prj1 --output_dir out_dir/


作業ガイド画像もダウンロードする場合は、``--download_image`` を指定してください。
その場合、img要素のsrc属性値はローカルの画像を参照します。


.. code-block::

    $ annofabcli instruction download --project_id prj1 --output_dir out_dir/ --download_image



デフォルトでは最新の作業ガイドをダウンロードします。過去のアノテーション作業ガイドをダウンロードする場合は、``--before`` または ``--history_id`` を指定してください。
history_idは、`annofabcli instruction list_history <../instruction/list_history.html>`_ コマンドで取得できます。

以下のコマンドは、最新より1つ前の作業ガイドを出力します。

.. code-block::

    $ annofabcli instruction download --project_id prj1 --before 1


以下のコマンドは、history_idが"xxx"のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli instruction download --project_id prj1 --history_id xxx





出力結果
=================================

htmlファイルのみダウンロードする場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli instruction download --project_id prj1 --output_dir out_dir

.. code-block::

    out_dir
    └── index.html


画像ファイルもダウンロードする場合
--------------------------------------------------------------------------------------------
.. code-block::

    $ annofabcli instruction download --project_id prj1 --output_dir out_dir --download_image

.. code-block::

    out_dir
    ├── img
    │   ├── aaeeabee-9403-4ad9-a221-16a0c37cdfc0
    │   └── d48fb417-8d20-4f00-9c50-d35e27b760e2
    │   ...
    └── index.html

Usage Details
=================================

.. argparse::
   :ref: annofabcli.instruction.download_instruction.add_parser
   :prog: annofabcli instruction download
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli instruction list_history <../instruction/list_history.html>`_

