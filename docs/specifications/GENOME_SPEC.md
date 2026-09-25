# Genome Specification — v0.1

Genomeは「種名」や「進化先」ではなく、個体の生命活動を規定する連続値パラメータ群として扱う。

## v0.1 genes

- `speed` — 1 tickあたりの最大移動量
- `sensor_range` — 資源を知覚できる距離
- `metabolism` — 生存の基礎エネルギー消費
- `movement_cost` — 移動距離あたりのエネルギー消費
- `reproduction_threshold` — 生殖開始エネルギー
- `offspring_fraction` — 親から子へ分配するエネルギー割合
- `mutation_scale` — 突然変異の相対標準偏差（下記参照）。この値自身も変異する
- `max_age` — 最大寿命（整数）

## Mutation

子個体生成時、各遺伝子 `v` は親の `mutation_scale = s` を使って独立に次の変異を受ける（遺伝子の順序は `Genome` のフィールド順で、乱数の消費順も固定）。

```text
v' = clamp(v × (1 + N(0, s)), lo, hi)
```

- **乗法的（相対的）ガウス変異。** `s` は絶対値ではなく、値に対する相対標準偏差である。
- **`mutation_scale` は自己適応的。** `s` 自身も同じ式で変異する。
- **clamp 範囲**は `eyggnx.genome.GENE_BOUNDS` にある。すべての run record に記録される。
- **`max_age`** は変異後に整数へ丸める。値が小さく `s` も小さいと、多くの変異が丸めで元の値に戻る（例: 80 / 0.005 では約 89% が変化なし）。
- **創始個体**は既定 Genome から1回だけ変異して作られる。`SimulationConfig(mutate_offspring=False)` にすると、その後の子は親 Genome をそのままコピーする（固定ゲノム対照）。

### 既知の偏り（解釈上の注意）

- **中立ドリフトは下向き。** `E[log(1 + ε)] < 0` と clamp の影響で、選択なしでも遺伝値は下がる。300 世代の変異のみの系統では、`speed` の中央値が 1.0 から約 0.65 まで下がる。形質の減少を「適応」と呼ぶ前に、`python -m eyggnx.controls` の中立ドリフト基準と比較すること。
- **コストのない遺伝子は clamp 境界へ張り付く。** 現モデルでは `metabolism` を下げる、`max_age` を伸ばす、`sensor_range` を広げることに対価がない。長時間の実行ではこれらが境界へ移動する（例: `metabolism` は 30,000 tick で下限 0.05 に張り付く）。この場合の到達点は環境ではなく境界値が決めている。境界への集中度は recorder の `frac_at_lower` / `frac_at_upper` で観測できる。

固定進化ツリーは持たない。将来は遺伝子追加・削除、可変長Genome、器官発生ルール、遺伝子重複、水平伝播へ拡張する。
