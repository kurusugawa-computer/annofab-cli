=================================
instruction download
=================================

Description
=================================
作業ガイドのHTMLをダウンロードします。



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


出力ディレクトリは以下のような構成になります

.. code-block::

    out_dir
    ├── img
    │   ├── aaeeabee-9403-4ad9-a221-16a0c37cdfc0
    │   └── d48fb417-8d20-4f00-9c50-d35e27b760e2
    │   ...
    └── index.html


