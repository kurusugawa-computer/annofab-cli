=================================
instruction upload
=================================

Description
=================================
HTMLファイルを作業ガイドとして登録します。



Examples
=================================

基本的な使い方
--------------------------
作業ガイドとして登録するHTMLファイルのパスを、``--html`` に指定してください。
img要素のsrc属性がローカルの画像を参照している場合（http, https, dataスキーマが付与されていない）は、画像も作業ガイドの画像としてアップロードします。


.. code-block:: html
    :caption: instruction.html

    <html>
    <head></head>
    <body>
    作業ガイドのサンプル
    <img src="lenan.png">
    </body>
    </html>


.. code-block::

    $ annofabcli instruction upload --project_id prj1 --html instruction.html


補足：ConfluenceのページをAnnofabの作業ガイドとして登録する
------------------------------------------------------------------------
以下の手順に従って、HTMLファイルを作成してください。

1. Confluenceのエクスポート機能で、作業ガイドに登録したいページをエクスポートする。
2. エクスポートしたzipに格納されている ``site.css`` を https://raw.githubusercontent.com/kurusugawa-computer/annofab-cli/main/docs/command_reference/instruction/upload/site.css に置き換える。
   デフォルトの状態では、表の罫線や背景色が表示されていないため。
3. エクスポートしたHTMLのスタイルを、style属性に反映する。Annofabの作業ガイドには、スタイルシートを登録できないため。

   1. エクスポートしたファイルをChromeで開く。
   2. Chrome開発ツールのConfoleタブで以下のJavaScriptを実行して、表関係の要素スタイルをstyle属性に反映させる。
   
   .. code-block:: javascript
   
       elms = document.querySelectorAll("table,thead,tbody,tfoot,caption,colgroup,col,tr,td,th");
       for (let e of elms) {
           s = window.getComputedStyle(e);
           e.style.background = s.background;
           e.style.color = s.color;
           e.style.border = s.border;
           e.style.borderCollapse = s.borderCollapse
       }
   
   1. Chrome開発ツールのElementタブで、html要素をコピー(Copy outerHTML)して、HTMLファイルを上書きする。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.instruction.upload_instruction.add_parser
   :prog: annofabcli instruction upload
   :nosubcommands:
   :nodefaultconst:
