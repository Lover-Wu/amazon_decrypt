# 步骤

1、打开excel，读取第Y列的asin编码，标题为“1 前三ASIN”（需要去掉第一行的标题）
2、按照https://www.amazon.com/bp/+asin码组合链接，例如https://www.amazon.com/dp/B0DQKSVC1B
3、访问各个链接
4、爬取主要内容，标题，五点描述，价格，属性
4.1、参照sellerSpirit的方法，访问Amazon
4.2、 用accessible tree获取需要信息的xpath

```xpath
标题:  //span[@id='productTitle']  
五点描述:  //div[@id='feature-bullets']

价格: （有两个，其中一个可以匹配）
//div[@id='apex_desktop_newAccordionRow']//div[@id='corePriceDisplay_desktop_feature_div']//span[@aria-hidden='true']  
//span[@class='a-price aok-align-center reinventPricePriceToPayMargin priceToPay']//span[@aria-hidden='true']  

商品信息：//div[@id='prodDetails']

```

5、保存为json文件

# Bug
- 有时候有的商品属性表通过xpath抓取不到，返回空


## 示例原始信息

需要进行整理

五点描述：

```
About this item                         【𝟵𝟵 𝗞𝗲𝘆𝘀 𝟵𝟲% 𝗟𝗮𝘆𝗼𝘂𝘁 】The 99 key layout reduces the size to 39x13.5x4cm while ensuring full keyboard functionality. Paired with pluggable USB-C (connect keyboard) to USB-A (connect PC) cable, the keyboard can save your desktop space, improve work efficiency, and game performance.     【𝗛𝗼𝘁-𝘀𝘄𝗮𝗽𝗽𝗮𝗯𝗹𝗲 𝗖𝘂𝘀𝘁𝗼𝗺 𝗞𝗲𝘆𝗯𝗼𝗮𝗿𝗱】The switches and keycaps can be freely replaced(keycap/switch puller are included in the package).This customizable keyboard with hot-swap PCB allows users to replace 3 pins/5 pins switches easily without soldering issue. Z-99 mechanical keyboards equipped with pre-lubed linear switches, bring smooth typing feeling and pleasant typing sound, provide fast response for exciting game.     【𝗚𝗮𝘀𝗸𝗲𝘁 𝗦𝘁𝗿𝘂𝗰𝘁𝘂𝗿𝗲 𝘄𝗶𝘁𝗵 𝗦𝗼𝘂𝗻𝗱 𝗔𝗯𝘀𝗼𝗿𝗯𝗶𝗻𝗴 𝗙𝗼𝗮𝗺𝘀】- GASKET structure ensures the highest quality assurance with great durability and stable performance. Equipped with 4 layers of thicker sound-absorbing foams, silicone dampener pad, which reduces 40% noise and removes 80% hallow sound. Bringing creamy sounding, natural and clear feedback, no more cavities noise.     【𝗙𝘂𝗹𝗹𝘆 𝗔𝗻𝘁𝗶-𝗴𝗵𝗼𝘀𝘁】100% anti-ghosting 99 keys deliver reliably accurate performance without any program error. N-key rollover, keyboard can respond to multiple key presses at the same time, which is helpful in very exciting real-time games.     【𝗖𝗼𝗼𝗹 𝗥𝗚𝗕 𝗕𝗮𝗰𝗸𝗹𝗶𝘁 𝗘𝗳𝗳𝗲𝗰𝘁】 Z-99 RGB keyboard include 15 backlight effects and 8 solid backlight color switching. Different RGB setting enriches your typing time. Lighting speed and level can also be adjusted according to your need. Double shot Injection PBT Keycaps, character never fade.     【 𝗣𝗿𝗼 𝗦𝗼𝗳𝘁𝘄𝗮𝗿𝗲 𝗦𝘂𝗽𝗽𝗼𝗿𝘁𝗲𝗱】 Expand your options using the available software to design your own new modes and effects. Macros with different keybindings or shortcuts for more efficient work and gaming. Software link: bit.ly/Z-99WiredDriver       
                     ›  See more product details
```



### About this item

### 【９９ Keys ９２％ Layout】
- The 99 key layout reduces the size to 39x13.5x4cm while ensuring full keyboard functionality.
- Paired with pluggable USB-C (connect keyboard) to USB-A (connect PC) cable, the keyboard can save your desktop space, improve work efficiency, and game performance.

#### 【Hot-swappable Custom Keyboard】
- The switches and keycaps can be freely replaced (keycap/switch puller are included in the package).
- This customizable keyboard with hot-swap PCB allows users to replace 3 pins/5 pins switches easily without soldering issue.
- Z-99 mechanical keyboards equipped with pre-lubed linear switches, bring smooth typing feeling and pleasant typing sound, provide fast response for exciting game.

#### 【Gasket Structure with Sound Absorbing Foams】
- Gasket structure ensures the highest quality assurance with great durability and stable performance.
- Equipped with 4 layers of thicker sound-absorbing foams, silicone dampener pad, which reduces 40% noise and removes 80% hollow sound.
- Bringing creamy sounding, natural and clear feedback, no more cavities noise.

#### 【Fully Anti-Ghost】
- 100% anti-ghosting 99 keys deliver reliably accurate performance without any program error.
- N-key rollover, keyboard can respond to multiple key presses at the same time, which is helpful in very exciting real-time games.

#### 【Cool RGB Backlit Effect】
- Z-99 RGB keyboard include 15 backlight effects and 8 solid backlight color switching.
- Different RGB setting enriches your typing time.
- Lighting speed and level can also be adjusted according to your need.
- Double shot Injection PBT Keycaps, character never fade.

#### 【Pro Software Supported】
- Expand your options using the available software to design your own new modes and effects.
- Macros with different keybindings or shortcuts for more efficient work and gaming.
- Software link: bit.ly/Z-99WiredDriver





商品信息：

- 需要先筛除掉无用的html噪音

- 需要根据语义整理标题和属性键值对，如{"Connectivity Technology":" USB-A, USB-C ","Button Quantity ":"99"}

- 有多个属性表，可能的表名称 **Features & Specs** 、 **Style** 、**Item details**、**Additional details**、**Material& Care**、**User guide**、**Measurement**、**Item detals**、

- 根据空格可以复原出结构， 一个空格为单词空格，不做处理; 根据21个空格分离出键值对，根据13个空格分离键和值

- | 连续空格数量 | 出现次数 | 结构意义判断             |
  | ------------ | -------- | ------------------------ |
  | 1            | 32       | 普通词内 / 非结构空格    |
  | 3            | 1        | 噪声或轻度对齐           |
  | 9            | 13       | **字段列分隔（高频）**   |
  | 10           | 1        | 列分隔变体               |
  | 16           | 1        | 列 / 区块级分隔          |
  | 18           | 2        | **强分隔（大字段跳转）** |
  | 21           | 13       | **字段列分隔（高频）**   |

- 

  [原地址](https://www.amazon.com/HUO-JI-Mechanical-Swappable-Pre-lubed/dp/B0D3LPNN9N/?_encoding=UTF8&pd_rd_w=gmWix&content-id=amzn1.sym.048a6e3c-8d40-4302-8312-26c626af6738%3Aamzn1.symc.050ea944-f1cf-4610-b462-3b604f2f4082&pf_rd_p=048a6e3c-8d40-4302-8312-26c626af6738&pf_rd_r=6PCHVGDB3ZTT0895G54M&pd_rd_wg=qmv6N&pd_rd_r=091f0698-bb6e-4291-940e-f6bc933c7f62&ref_=pd_hp_d_btf_ci_mcx_mr_ca_id_hp_d&th=1)

```feature
    Product information                       {"voyager-desktop-treatment":"T1","product_type":"KEYBOARDS"}                    Features & Specs                  Compatible Devices         Gaming Console, Laptop, PC, PS, XBOX                     Connectivity Technology         USB-A, USB-C                     Additional Features         Backlit, Creamy sound, Ergonomic, Gasket Structure, Hot-Swappable                     Number of Keys         99                     Keyboard Backlighting Color Support         RGB                     Language         English                     Power Source         Corded Electric                     Switch Type         Linear                     Keyboard Layout         QWERTY                     Hand Orientation         Ambidextrous                     Button Quantity         99                     Mechanical Keyboard Switch Model         outemu_silent_gray                Style                  Color          White                     Style Name         Classic                     Theme         [Inferred: gaming, creamy white design]                       
        Warranty & Support             Product Warranty: For warranty information about this product, please click here     
             Feedback                                                               
        .grid-container {


        function getLoadingGifDiv() {
            return '<img src="https://images-na.ssl-images-amazon.com/images/G/01/x-locale/communities/tags/snake._CB485935600_.gif" class="loadingSymbolImage" width="16" height="16" border="0"/>';
        }

        function isValidUrl(url) {
            if (!url) {
                return false;
            }
            var encodedUrl = encodeURI(url);
            return encodedUrl.match(
                /^(https?:\/\/)?(([a-z0-9-]|%[A-F0-9]{2})+\.)+(([a-z]|%[A-F0-9]{2})([a-z0-9]|%[A-F0-9]{2})*)(:[0-9]+)?(\/[a-z0-9;:,~!+#@&=%\/$\.?_-]+)?$/i
            );
        }

        function isNumericPrice(price) {
            if (!price) {
                return false;
            }
            return price.match(/^([0-9]+\.?[0-9]*)$|^([0-9]*\.[0-9]+)$/);
        }

        function isEmptyValue(input) {
            return !input || input.length === 0 || input.match(/^\s*$/);
        }

        function truncate(input, length) {
            if (!input) {
                return '';
            } else {
                return input.substr(0, length);
            }
        }

        function formatDate(year, date, month) {
            return year + '-' + month + '-' + date;
        }

        function trim(input) {
            if (!input) {
                return '';
            } else {
                return input.trim();
            }
        }


                                          Item details                  Brand         HUO JI                     Keyboard Description         Mechanical                     Antenna Location         Business, Education, Everyday Use, Gaming, Multimedia, Personal, Photo Editing, Programming, Student, Video Editing                     Built-In Media         USB-A to USB-C Cable                     Manufacturer         HUO JI                     Customer Reviews                                
                                               
             4.6               4.6 out of 5 stars         

                         (524)      
                    
                    var dpAcrHasRegisteredArcLinkClickAction;
                    P.when('A', 'ready').execute(function(A) {
                        if (dpAcrHasRegisteredArcLinkClickAction !== true) {
                            dpAcrHasRegisteredArcLinkClickAction = true;
                            A.declarative(
                                'acrLink-click-metrics', 'click',
                                { "allowLinkDefault": true },
                                function (event) {
                                    if (window.ue) {
                                        ue.count("acrLinkClickCount", (ue.count("acrLinkClickCount") || 0) + 1);
                                    }
                                }
                            );
                        }
                    });
                
                 
            P.when('A', 'cf').execute(function(A) {
                A.declarative('acrStarsLink-click-metrics', 'click', { "allowLinkDefault" : true },  function(event){
                    if(window.ue) {
                        ue.count("acrStarsLinkWithPopoverClickCount", (ue.count("acrStarsLinkWithPopoverClickCount") || 0) + 1);
                    }
                });
            });
        

           
       4.6 out of 5 stars                    Best Sellers Rank      #76 in Computer Keyboards                         ASIN         B0D3LPNN9N                     Item Height         1.5 inches                     Item Weight         1.9 Pounds                     Unit Count         1.0 Count                     Warranty Description         1 year                Additional details                  Item Dimensions L x W x H         15.2"L x 5.3"W x 1.5"H                     Enclosure Material         Metal, Plastic
```







```
<div data-csa-c-content-id="voyager-expander-btn" data-csa-c-slot-id="voyager-expander-btn" data-csa-c-type="button" class="a-row a-expander-container a-expander-section-container a-section-expander-container" data-csa-c-id="r04059-xnit5b-wqtixx-jqk034">  <span class="a-declarative" data-action="voyager-expander-heading-toggle" data-voyager-expander-heading-toggle="{&quot;sectionIndex&quot;:0,&quot;columnName&quot;:&quot;depthRightSections&quot;}"> <a aria-expanded="true" role="button" href="javascript:void(0)" data-action="a-expander-toggle" class="a-expander-header a-declarative a-expander-section-header prodDet-expander-header-styling a-color-offset-background a-link-section-expander a-size-medium" data-a-expander-toggle="{&quot;allowLinkDefault&quot;:true, &quot;expand_prompt&quot;:&quot;&quot;, &quot;collapse_prompt&quot;:&quot;&quot;}" shub-ins="1" sh-att="1"><i class="a-icon a-icon-section-collapse"></i><span class="a-expander-prompt" role="heading" aria-level="5"> Measurements </span></a> </span> <div data-expanded="true" class="a-expander-content a-expander-extend-content a-expander-content-expanded" style="overflow: hidden;"> <div class="a-section">      <table class="a-keyvalue prodDetTable"> <tbody><tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Item Dimensions D x W x H   </th>  <td class="a-size-base prodDetAttrValue">    27.5"D x 39.4"W x 29.5"H   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Number of Drawers   </th>  <td class="a-size-base prodDetAttrValue">    2   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Item Weight   </th>  <td class="a-size-base prodDetAttrValue">    24.25 Pounds   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Size   </th>  <td class="a-size-base prodDetAttrValue">    40 Inch   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Number Of Shelves   </th>  <td class="a-size-base prodDetAttrValue">    2   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Tabletop Thickness   </th>  <td class="a-size-base prodDetAttrValue">    0.75 Inches   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Maximum Height   </th>  <td class="a-size-base prodDetAttrValue">    29.5 Inches   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Minimum Height   </th>  <td class="a-size-base prodDetAttrValue">    75 Inches   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Working Surface Diagonal Length   </th>  <td class="a-size-base prodDetAttrValue">    48.5 Inches   </td> </tr> </tbody></table>  </div> </div> </div>


<div data-csa-c-content-id="voyager-expander-btn" data-csa-c-slot-id="voyager-expander-btn" data-csa-c-type="button" class="a-row a-expander-container a-expander-section-container a-section-expander-container" data-csa-c-id="sxqp4i-v4kvb-di646v-diornp">  <span class="a-declarative" data-action="voyager-expander-heading-toggle" data-voyager-expander-heading-toggle="{&quot;sectionIndex&quot;:1,&quot;columnName&quot;:&quot;depthRightSections&quot;}"> <a aria-expanded="true" role="button" href="javascript:void(0)" data-action="a-expander-toggle" class="a-expander-header a-declarative a-expander-section-header prodDet-expander-header-styling a-color-offset-background a-link-section-expander a-size-medium" data-a-expander-toggle="{&quot;allowLinkDefault&quot;:true, &quot;expand_prompt&quot;:&quot;&quot;, &quot;collapse_prompt&quot;:&quot;&quot;}"><i class="a-icon a-icon-section-collapse"></i><span class="a-expander-prompt" role="heading" aria-level="5"> Materials &amp; Care </span></a> </span> <div data-expanded="true" class="a-expander-content a-expander-extend-content a-expander-content-expanded" style="overflow: hidden;"> <div class="a-section">      <table class="a-keyvalue prodDetTable"> <tbody><tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Base   </th>  <td class="a-size-base prodDetAttrValue">    Metal   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Top Material Type   </th>  <td class="a-size-base prodDetAttrValue">    Engineered Wood   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Furniture Leg Material   </th>  <td class="a-size-base prodDetAttrValue">    Metal   </td> </tr> </tbody></table>  </div> </div> </div>

<div data-csa-c-content-id="voyager-expander-btn" data-csa-c-slot-id="voyager-expander-btn" data-csa-c-type="button" class="a-row a-expander-container a-expander-section-container a-section-expander-container" data-csa-c-id="n8qgmf-na3e5c-nyte3y-p417b5" xpath="1" style="">  <span class="a-declarative" data-action="voyager-expander-heading-toggle" data-voyager-expander-heading-toggle="{&quot;sectionIndex&quot;:2,&quot;columnName&quot;:&quot;depthRightSections&quot;}"> <a aria-expanded="true" role="button" href="javascript:void(0)" data-action="a-expander-toggle" class="a-expander-header a-declarative a-expander-section-header prodDet-expander-header-styling a-color-offset-background a-link-section-expander a-size-medium" data-a-expander-toggle="{&quot;allowLinkDefault&quot;:true, &quot;expand_prompt&quot;:&quot;&quot;, &quot;collapse_prompt&quot;:&quot;&quot;}"><i class="a-icon a-icon-section-collapse"></i><span class="a-expander-prompt" role="heading" aria-level="5"> Features &amp; Specs </span></a> </span> <div data-expanded="true" class="a-expander-content a-expander-extend-content a-expander-content-expanded" style="overflow: hidden;"> <div class="a-section">      <table class="a-keyvalue prodDetTable"> <tbody><tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Additional Features   </th>  <td class="a-size-base prodDetAttrValue">    Built-In USB Outlet, Reversible Shelves   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Mounting Type   </th>  <td class="a-size-base prodDetAttrValue">    Tabletop   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Drawer Type   </th>  <td class="a-size-base prodDetAttrValue">    Utility Drawer   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Base Type   </th>  <td class="a-size-base prodDetAttrValue">    Desk   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Has Finished Back   </th>  <td class="a-size-base prodDetAttrValue">    No   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Cabinet Configuration   </th>  <td class="a-size-base prodDetAttrValue">    Built-In   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Is Customizable?   </th>  <td class="a-size-base prodDetAttrValue">    No   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Is Electric   </th>  <td class="a-size-base prodDetAttrValue">    Yes   </td> </tr> </tbody></table>  </div> </div> </div>


```

- voyager-expander-btn

```
<div data-csa-c-content-id="voyager-expander-btn" data-csa-c-slot-id="voyager-expander-btn" data-csa-c-type="button" class="a-row a-expander-container a-expander-section-container a-section-expander-container" data-csa-c-id="xomnfg-65br93-kzvved-fu0fna">  <span class="a-declarative" data-action="voyager-expander-heading-toggle" data-voyager-expander-heading-toggle="{&quot;sectionIndex&quot;:0,&quot;columnName&quot;:&quot;depthRightSections&quot;}"> <a aria-expanded="true" role="button" href="javascript:void(0)" data-action="a-expander-toggle" class="a-expander-header a-declarative a-expander-section-header prodDet-expander-header-styling a-color-offset-background a-link-section-expander a-size-medium" data-a-expander-toggle="{&quot;allowLinkDefault&quot;:true, &quot;expand_prompt&quot;:&quot;&quot;, &quot;collapse_prompt&quot;:&quot;&quot;}" xpath="1"><i class="a-icon a-icon-section-collapse"></i><span class="a-expander-prompt" role="heading" aria-level="5"> Item details </span></a> </span> <div data-expanded="true" class="a-expander-content a-expander-extend-content a-expander-content-expanded" style="overflow: hidden;"> <div class="a-section">      <table class="a-keyvalue prodDetTable"> <tbody><tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Brand   </th>  <td class="a-size-base prodDetAttrValue">    HUO JI   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Keyboard Description   </th>  <td class="a-size-base prodDetAttrValue">    Mechanical   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Antenna Location   </th>  <td class="a-size-base prodDetAttrValue">    Business, Education, Everyday Use, Gaming, Multimedia, Personal, Photo Editing, Programming, Student, Video Editing   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Built-In Media   </th>  <td class="a-size-base prodDetAttrValue">    USB-A to USB-C Cable   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Manufacturer   </th>  <td class="a-size-base prodDetAttrValue">    HUO JI   </td> </tr>              <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">Customer Reviews</th>  <td class="a-size-base">                              <div id="averageCustomerReviews" data-asin="B0D3LPNN9N" data-ref="dpx_acr_pop_">
                              <span class="a-declarative" data-action="acrStarsLink-click-metrics" data-acrstarslink-click-metrics="{}">                 <span id="acrPopover" class="reviewCountTextLinkedHistogram noUnderline" title="4.6 out of 5 stars">
        <span class="a-declarative" data-action="a-popover" data-a-popover="{&quot;position&quot;:&quot;triggerBottom&quot;,&quot;popoverLabel&quot;:&quot;Customer Reviews Ratings Summary&quot;,&quot;max-width&quot;:&quot;700&quot;,&quot;closeButton&quot;:&quot;true&quot;,&quot;closeButtonLabel&quot;:&quot;Close&quot;,&quot;url&quot;:&quot;/gp/customer-reviews/widgets/average-customer-review/popover/ref=dpx_acr_pop_?contextId=dpx&amp;asin=B0D3LPNN9N&quot;}"> <a href="javascript:void(0)" role="button" class="a-popover-trigger a-declarative mvt-cm-cr-review-stars-mini-popover">   <span aria-hidden="true" class="a-size-small a-color-base"> 4.6 </span>              <i class="a-icon a-icon-star-mini a-star-mini-4-5 mvt-cm-cr-review-stars-mini"><span class="a-icon-alt">4.6 out of 5 stars</span></i>     <i class="a-icon a-icon-popover"></i></a> </span>   </span>

       </span> <span class="a-letter-space"></span>             <span class="a-declarative" data-action="acrLink-click-metrics" data-acrlink-click-metrics="{}"> <a id="acrCustomerReviewLink" class="a-link-normal" href="#averageCustomerReviewsAnchor">   <span id="acrCustomerReviewText" aria-label="524 Reviews" class="a-size-small">(524)</span>    </a> </span> <script type="text/javascript">
                    
                    var dpAcrHasRegisteredArcLinkClickAction;
                    P.when('A', 'ready').execute(function(A) {
                        if (dpAcrHasRegisteredArcLinkClickAction !== true) {
                            dpAcrHasRegisteredArcLinkClickAction = true;
                            A.declarative(
                                'acrLink-click-metrics', 'click',
                                { "allowLinkDefault": true },
                                function (event) {
                                    if (window.ue) {
                                        ue.count("acrLinkClickCount", (ue.count("acrLinkClickCount") || 0) + 1);
                                    }
                                }
                            );
                        }
                    });
                </script>
                 <script type="text/javascript">
            P.when('A', 'cf').execute(function(A) {
                A.declarative('acrStarsLink-click-metrics', 'click', { "allowLinkDefault" : true },  function(event){
                    if(window.ue) {
                        ue.count("acrStarsLinkWithPopoverClickCount", (ue.count("acrStarsLinkWithPopoverClickCount") || 0) + 1);
                    }
                });
            });
        </script>

           </div>
      <br> 4.6 out of 5 stars </td> </tr>                <tr> <th class="a-color-secondary a-size-base prodDetSectionEntry"> Best Sellers Rank </th> <td> <span> <ul class="a-unordered-list a-nostyle a-vertical">  <li><span class="a-list-item"><span>#74 in <a href="/gp/bestsellers/pc/12879431/ref=pd_zg_hrsr_pc">Computer Keyboards</a></span></span></li>  </ul> </span> </td> </tr>             <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    ASIN   </th>  <td class="a-size-base prodDetAttrValue">    B0D3LPNN9N   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Item Height   </th>  <td class="a-size-base prodDetAttrValue">    1.5 inches   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Item Weight   </th>  <td class="a-size-base prodDetAttrValue">    1.9 Pounds   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Unit Count   </th>  <td class="a-size-base prodDetAttrValue">    1.0 Count   </td> </tr>          <tr>   <th class="a-color-secondary a-size-base prodDetSectionEntry">    Warranty Description   </th>  <td class="a-size-base prodDetAttrValue">    1 year   </td> </tr> </tbody></table>  </div> </div> </div>
```

//div[@id='productDetails_expanderTables_depthRightSections']//div[2]

//div[@id='productDetails_expanderTables_depthLeftSections']//div[2]

//div[@id='productDetails_expanderTables_depthLeftSections']//div[1]

左右的1都有重复的问题。

直接用 //div[@id='productDetails_expanderTables_depthLeftSections'] 和  //div[@id='productDetails_expanderTables_depthRightSections']

```
Style                  Shape         Rectangular                     Desk Design         Computer Desk                     Color         Wood Black                     Style Name         Modern                     Finish Types         Wood                     Furniture Finish         Wood Black                     Top Color         Black                

Materials & Care                  Base         Metal                     Top Material Type         Wood                     Furniture Leg Material         Metal                

Features & Specs                  Additional Features         Easy Clean                     Mounting Type         Floor Mount                     Drawer Type         Single Drawer                     Base Type         Leg                     Frame Joint Type         Metal                     Storage Options         Storage pockets, 1 multifunctional hook                     Is Customizable?         No                     Is Electric         No               

User guide                  Required Assembly         Yes                     Maximum Weight Recommendation         265 Pounds                     Recommended Number of People for Assembly         2                     Warranty Type         Limited                     UL Listed         No                     Tools Recommended For Assembly         Screw Driver                     Mfg Warranty Type (i.e. Parts, Labor)         limited warranty                     Includes All Assembly Tools         Yes


Measurements                  Item Dimensions D x W x H         19.69"D x 32"W x 29.73"H                     Size         32 Inch                     Number Of Shelves         1                     Maximum Height         29.8 Inches                     Working Surface Diagonal Length         39.8 Inches         
Item details                  Brand Name         DUMOS                     Room Type         Bedroom, Office                     Recommended Uses For Product         Office, Gaming                     Age Range Description         Adult                     Included Components         Home Office Desk                     Product Grade         new                     Model Number         DUM32BK                     Model Name         DUMOS 32 Inch Office Small Computer Desk                     UPC         719406413948                     Manufacturer         DUMOS                     Customer Reviews                                
                                               
             4.6               4.6 out of 5 stars         

                         (2,667)      
                    
                    var dpAcrHasRegisteredArcLinkClickAction;
                    P.when('A', 'ready').execute(function(A) {
                        if (dpAcrHasRegisteredArcLinkClickAction !== true) {
                            dpAcrHasRegisteredArcLinkClickAction = true;
                            A.declarative(
                                'acrLink-click-metrics', 'click',
                                { "allowLinkDefault": true },
                                function (event) {
                                    if (window.ue) {
                                        ue.count("acrLinkClickCount", (ue.count("acrLinkClickCount") || 0) + 1);
                                    }
                                }
                            );
                        }
                    });
                
                 
            P.when('A', 'cf').execute(function(A) {
                A.declarative('acrStarsLink-click-metrics', 'click', { "allowLinkDefault" : true },  function(event){
                    if(window.ue) {
                        ue.count("acrStarsLinkWithPopoverClickCount", (ue.count("acrStarsLinkWithPopoverClickCount") || 0) + 1);
                    }
                });
            });
        

           
       4.6 out of 5 stars                    Best Sellers Rank      #900 in Home & Kitchen (See Top 100 in Home & Kitchen)  #1 in Home Office Desks                         ASIN         B0DQKSVC1B                     Item Type Name         Modern Simple Style Writing Study Work Table for Home Bedroom - Wood Black                     Item Height         29.8 inches


```



# A+ 页图片下载

根据一些标签可以爬取

aplus-premium-module-2-fullbackground-image

- 如果显示，可以直接照搬outHtml
- 也可以根据链接下载

## 实战建议

### ✅ **最佳实践**

1. **优先使用稳定特征**（如 `aplus`）
2. **组合多个条件**提高准确性
3. **降级策略**确保兜底
4. **基于内容过滤**（如 src 包含特定字符串）

### ⚠️ **避免的做法**

```
# ❌ 过于精确（容易失效）
xpath = '//div[@class="a-section a-spacing-none aplus-card-image"]'

# ✅ 应该用包含匹配
xpath = '//div[contains(@class, "aplus-card-image")]'
```

### 📌 **调试技巧**

```
# 打印所有可能的容器，分析规律
containers = page.eles('xpath://div[contains(@class, "aplus")]')
for i, container in enumerate(containers):
    print(f"容器{i}: {container.attr('class')}")
    imgs = container.eles('tag:img')
    print(f"  图片数量: {len(imgs)}")
```



<div class="a-section a-spacing-none background-image">                                    <img alt="8" src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/d07dadea-6a16-437b-9d95-62be7fd205c0.__CR0,0,1464,600_PT0_SX1464_V1___.jpg" class="" data-src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/d07dadea-6a16-437b-9d95-62be7fd205c0.__CR0,0,1464,600_PT0_SX1464_V1___.jpg" style="">  </div>



<div class="celwidget aplus-module premium-module-2-fullbackground-image aplus-premium" cel_widget_id="aplus-premium-module-2-fullbackground-image" data-csa-c-id="f74o13-jym898-l0zvd5-hjtaxm" data-cel-widget="aplus-premium-module-2-fullbackground-image">
                             <div class="a-section a-spacing-none premium-aplus premium-aplus-module-2">                                   <div class="a-section a-spacing-none premium-background-wrapper">  <div class="a-section a-spacing-none background-image">                                    <img alt="8" src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/d07dadea-6a16-437b-9d95-62be7fd205c0.__CR0,0,1464,600_PT0_SX1464_V1___.jpg" class="" data-src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/d07dadea-6a16-437b-9d95-62be7fd205c0.__CR0,0,1464,600_PT0_SX1464_V1___.jpg" style=""><noscript><img alt="8" src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/d07dadea-6a16-437b-9d95-62be7fd205c0.__CR0,0,1464,600_PT0_SX1464_V1___.jpg"/></noscript>  </div>   </div> <div class="a-section a-text-center">                                  </div> </div>      </div>



<div class="celwidget aplus-module premium-module-2-fullbackground-image aplus-premium" cel_widget_id="aplus-premium-module-2-fullbackground-image" data-csa-c-id="q08jnd-8ghbfa-obtpns-okttr3" data-cel-widget="aplus-premium-module-2-fullbackground-image">
                             <div class="a-section a-spacing-none premium-aplus premium-aplus-module-2">                                   <div class="a-section a-spacing-none premium-background-wrapper">  <div class="a-section a-spacing-none background-image">                                    <img alt="1" src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/6c5f3dae-9ff9-45c3-92a4-8442871b30b6.__CR0,0,1464,600_PT0_SX1464_V1___.jpg" class="" data-src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/6c5f3dae-9ff9-45c3-92a4-8442871b30b6.__CR0,0,1464,600_PT0_SX1464_V1___.jpg"><noscript><img alt="1" src="https://m.media-amazon.com/images/S/aplus-media-library-service-media/6c5f3dae-9ff9-45c3-92a4-8442871b30b6.__CR0,0,1464,600_PT0_SX1464_V1___.jpg"/></noscript>  </div>   </div> <div class="a-section a-text-center">                                  </div> </div>      </div>





