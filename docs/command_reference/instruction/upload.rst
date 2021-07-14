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


補足：ConfluenceのページをAnnoFabの作業ガイドとして登録する
------------------------------------------------------------------------
以下の手順に従って、HTMLファイルを作成してください。

1. Confluenceのエクスポート機能で、作業ガイドに登録したいページをエクスポートする。
2. エクスポートしたzipに格納されている ``site.css`` を https://raw.githubusercontent.com/kurusugawa-computer/annofab-cli/master/docs/instruction/upload/site.css に置き換える。
   デフォルトの状態では、表の罫線や背景色が表示されていないため。
3. エクスポートしたHTMLのスタイルを、style属性に反映する。AnnoFabの作業ガイドには、スタイルシートを登録できないため。

   1. エクスポートしたファイルをChromeで開く。
   2. Chrome開発ツールのConfoleタブで以下のJavaScriptを実行して、全要素のborder, color, backgroundスタイルを、style属性に反映させる。
   
   .. code-block:: javascript
   
       elms = document.querySelectorAll("body *");
       for (let e of elms) {
           s = window.getComputedStyle(e);
           e.style.background = s.background;
           e.style.color = s.color;
           e.style.border = s.border;
       }
   
   1. Chrome開発ツールのElementタブで、html要素をコピー(Copy outerHTML)して、HTMLファイルを上書きする。



