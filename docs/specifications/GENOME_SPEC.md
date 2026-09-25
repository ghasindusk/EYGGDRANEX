# Genome Specification — v0.1

Genomeは「種名」や「進化先」ではなく、個体の生命活動を規定する連続値パラメータ群として扱う。

## v0.1 genes

- `speed` — 1 tickあたりの最大移動量
- `sensor_range` — 資源を知覚できる距離
- `metabolism` — 生存の基礎エネルギー消費
- `movement_cost` — 移動距離あたりのエネルギー消費
- `reproduction_threshold` — 生殖開始エネルギー
- `offspring_fraction` — 親から子へ分配するエネルギー割合
- `mutation_scale` — 突然変異の標準偏差
- `max_age` — 最大寿命

## Mutation

各遺伝子は子個体生成時に独立したガウス変異を受ける。値は生物学的・数値的破綻を避けるため各遺伝子の許容域へclampする。

固定進化ツリーは持たない。将来は遺伝子追加・削除、可変長Genome、器官発生ルール、遺伝子重複、水平伝播へ拡張する。
