# Bill of Materials (BOM)

| Ref | Qty | Value / Part# | Description | Vendor |
|---|---|---|---|---|
| C1, C2 | 2 | 22pF p2.5mm | セラミックコンデンサ | |
| C3 | 1 | 4.7uF p1.5mm (φ4mm) | 電解コンデンサ | [秋月電子](https://akizukidenshi.com/catalog/g/g117895/) |
| C4, C5 | 2 | 100nF p5.0mm | 積層セラミックコンデンサ | |
| D1-D48 | 48 | 1N4148 | ダイオード | [秋月電子](https://akizukidenshi.com/catalog/g/g100941/) |
| D49, D50 | 2 | 3.6V | ツェナーダイオード | [秋月電子](https://akizukidenshi.com/catalog/g/g115719/) |
| F1 | 1 | 100mA | ポリスイッチ | [秋月電子](https://akizukidenshi.com/catalog/g/g112911/) |
| J1 | 1 | TYPE-C-31-M-12 | USB Type-C コネクタ（裏面実装） | [Amazon](https://www.amazon.co.jp/dp/B09PKH9XZY) |
| J2 | 1 | 2x3 p2.54mm | AVR ISP ピンヘッダ（任意） | |
| LED1, LED2 | 2 | 3mm | LED（LED1=Caps Lock, LED2=レイヤー） | [秋月電子 黄緑](https://akizukidenshi.com/catalog/g/g111637/) / [赤](https://akizukidenshi.com/catalog/g/g111577/) |
| MX1-MX48 | 48 | Kailh CPG151101S11 | MX 用ホットスワップソケット（裏面）。JLCPCB 実装なら LCSC C41430893（互換品） | |
| (switch) | 48 | MX 互換 | キースイッチ（3pin / 5pin どちらも可） | |
| R1, R7, R8 | 3 | 1.5kΩ | 抵抗 | [秋月電子](https://akizukidenshi.com/catalog/g/g116632/) |
| R2, R3 | 2 | 75Ω | 抵抗 | [秋月電子](https://akizukidenshi.com/catalog/g/g116620/) |
| R4 | 1 | 10kΩ | 抵抗 | [秋月電子](https://akizukidenshi.com/catalog/g/g108550/) |
| R5, R6 | 2 | 5.1kΩ | 抵抗（USB-C CC） | [秋月電子](https://akizukidenshi.com/catalog/g/g108547/) |
| SW1, SW2 | 2 | 6x6mm | タクトスイッチ（RESET / BOOT） | [Mouser](https://www.mouser.jp/ProductDetail/611-645SL70SMTR92LFS) |
| U1 | 1 | ATMEGA328P-PU | マイコン | [Mouser](https://www.mouser.jp/ProductDetail/556-ATMEGA328P-PU) / [秋月電子](https://akizukidenshi.com/catalog/g/g103142/) |
| (U1) | 1 | 28pin narrow | IC ソケット | [秋月電子](https://akizukidenshi.com/catalog/g/g100013/) |
| Y1 | 1 | HC49-4H 16MHz | 水晶振動子 | [Mouser](https://www.mouser.jp/ProductDetail/449-LFXTAL022786BULK) |
| plate | 2 | `gerbers/eugeo-plate.zip` または `lasercut/yushakobo/eugeo-switch-plate_*.svg` | スイッチプレート（左右共通、FR4 1.5mm または POM 1.5mm） | JLCPCB / [遊舎工房](https://shop.yushakobo.jp/products/lasercut-2) |
| case | 1 | `case/eugeo-case.step` | ケース（JLC3DP SLA レジン） | |
| standoff | 8 | M2 3.5mm メス-メス | PCB - プレート間（1.5mm 厚プレートの場合） | |
| screw | 8 | M2×10 なべ | ケース底 → PCB → スペーサー | |
| screw | 8 | M2×3 | プレート → スペーサー（任意） | |
| feet | 4〜6 | ゴム足 | ケース底のふちに貼る | |
| cover | 1 | `lasercut/yushakobo/eugeo-cover_*.svg` | 中央カバー（アクリル クリア 2mm、遊舎工房レーザー加工） | [遊舎工房](https://shop.yushakobo.jp/products/lasercut) |
| standoff | 4 | M2 10mm メス-メス | PCB - 中央カバー間 | |
| screw | 8 | M2×4 | 中央カバーのスペーサー固定（PCB 下 4 本 + カバー上 4 本） | |
| plate foam | 2 | 3mm PORON | `foam/eugeo-plate-foam`（任意） | [遊舎工房](https://shop.yushakobo.jp/products/lasercut-2) |
| case foam | 2 | 3mm PORON | `foam/eugeo-case-foam`（任意） | [遊舎工房](https://shop.yushakobo.jp/products/lasercut-2) |

ケースを使わない場合は、ケースの代わりにボトムプレート（`gerbers/eugeo-bottom.zip`）、PCB とボトムの間に M2 8mm スペーサー 8 本、M2×4 ネジ 16 本を使います。

ホットスワップ基板なので、スイッチはプレートで固定する前提です。
