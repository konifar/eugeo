# Bill of Materials (BOM)

| Ref | Qty | Value / Part# | Description | Vendor |
|---|---|---|---|---|
| U1, U2, U4, C10-C15, C17, C18, C20, C22, R11 | — | 下表 | 表面実装部品（JLCPCB が実装） | `jlcpcb/eugeo-bom.csv` |
| C1, C2 | 2 | 22pF p2.5mm | セラミックコンデンサ（水晶の負荷容量） | |
| C3 | 1 | 10uF p1.5mm (φ4mm) | 電解コンデンサ（+5V） | |
| C6, C7 | 2 | 1uF p2.5mm | 積層セラミックコンデンサ（MCP1700 の入力 / 出力） | |
| D1-D48 | 48 | 1N4148 | ダイオード | [秋月電子](https://akizukidenshi.com/catalog/g/g100941/) |
| F1 | 1 | 100mA | ポリスイッチ | [秋月電子](https://akizukidenshi.com/catalog/g/g112911/) |
| J1 | 1 | TYPE-C-31-M-12 | USB Type-C コネクタ（裏面実装） | [Amazon](https://www.amazon.co.jp/dp/B09PKH9XZY) |
| LED1, LED2 | 2 | 3mm | LED（LED1=Caps Lock, LED2=レイヤー） | [秋月電子 黄緑](https://akizukidenshi.com/catalog/g/g111637/) / [赤](https://akizukidenshi.com/catalog/g/g111577/) |
| MX1-MX48 | 48 | Kailh CPG151101S11 | MX 用ホットスワップソケット（裏面）。JLCPCB 実装なら LCSC C41430893（互換品） | |
| (switch) | 48 | MX 互換 | キースイッチ（3pin / 5pin どちらも可） | |
| R2, R3 | 2 | 27Ω | 抵抗（USB D+ / D- 直列） | |
| R5, R6 | 2 | 5.1kΩ | 抵抗（USB-C CC） | [秋月電子](https://akizukidenshi.com/catalog/g/g108547/) |
| R7, R8, R10 | 3 | 1kΩ | 抵抗（LED 電流制限、BOOT） | |
| R9 | 1 | 10kΩ | 抵抗（RUN プルアップ） | [秋月電子](https://akizukidenshi.com/catalog/g/g108550/) |
| SW1, SW2 | 2 | 6x6mm | タクトスイッチ（RESET / BOOT） | [Mouser](https://www.mouser.jp/ProductDetail/611-645SL70SMTR92LFS) |
| U3 | 1 | MCP1700-3302E/TO | 3.3 V LDO（TO-92） | |
| Y1 | 1 | HC49-4H 12MHz | 水晶振動子 | |
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

## 表面実装部品（JLCPCB）

RP2040 まわりの表面実装部品は JLCPCB の PCBA で実装します（`jlcpcb/eugeo-bom.csv` / `eugeo-cpl.csv`）。C12 / C13 / U4 は裏面です。

| Ref | Qty | Value / Part# | LCSC | Description |
|---|---|---|---|---|
| U1 | 1 | RP2040 | C2040 | マイコン（QFN-56） |
| U2 | 1 | W25Q16JVSSIQ | C131025 | QSPI フラッシュ 2 MB（SOIC-8 208mil） |
| U4 | 1 | USBLC6-2SC6 | C7519 | USB ESD 保護（裏面） |
| C10-C15, C20, C22 | 8 | 100nF 0402 | C1525 | パスコン |
| C17, C18 | 2 | 1uF 0402 | C52923 | VREG_VIN / VREG_VOUT |
| R11 | 1 | 1kΩ 0402 | C11702 | 水晶の直列抵抗 |

