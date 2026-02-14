# usage/（回路設計例・チートシート）

このディレクトリは、7400シリーズICの **実回路例** と、汎用型番（`74xNN`）単位の **チートシート** を、カテゴリ別に統合して置きます。

## 構造

- `usage/{カテゴリ名}/{パーツ番号}/**.md`
  - 例: `usage/07_data_selectors_mux_demux/74x153/74x153.md`

## カテゴリ一覧

- [01_buffers_inverters/index.md](./01_buffers_inverters/index.md)
- [02_nand_and_gates/index.md](./02_nand_and_gates/index.md)
- [03_nor_or_gates/index.md](./03_nor_or_gates/index.md)
- [04_xor_xnor_gates/index.md](./04_xor_xnor_gates/index.md)
- [05_flipflops_latches/index.md](./05_flipflops_latches/index.md)
- [06_encoders_decoders/index.md](./06_encoders_decoders/index.md)
- [07_data_selectors_mux_demux/index.md](./07_data_selectors_mux_demux/index.md)
- [08_counters/index.md](./08_counters/index.md)
- [09_registers/index.md](./09_registers/index.md)
- [10_arithmetic/index.md](./10_arithmetic/index.md)
- [11_error_detection_correction/index.md](./11_error_detection_correction/index.md)
- [12_memory_storage/index.md](./12_memory_storage/index.md)
- [13_programmable_logic/index.md](./13_programmable_logic/index.md)
- [14_system_controllers_timing/index.md](./14_system_controllers_timing/index.md)
- [15_interfaces_links/index.md](./15_interfaces_links/index.md)
- [16_analog_mixed_signal/index.md](./16_analog_mixed_signal/index.md)
- [17_expanders/index.md](./17_expanders/index.md)
- [18_carry_generators/index.md](./18_carry_generators/index.md)
- [99_other/index.md](./99_other/index.md)

## チートシート（汎用型番）

- 生成元: [overview/7400_series_ic_overview.json](../overview/7400_series_ic_overview.json)
- 生成スクリプト: [scripts/generate_usage_cheatsheets.py](../scripts/generate_usage_cheatsheets.py)

> チートシートは「断定を避け、一次資料確認の導線を置く」方針です。

## 実回路例（例）

- [06_encoders_decoders/74x141/](./06_encoders_decoders/74x141/)
- [10_arithmetic/74x181,182/](./10_arithmetic/74x181,182/)
