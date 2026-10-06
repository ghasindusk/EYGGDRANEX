# GENESIS Experiments

最初の基準実験は `genesis-001`。

目的: 資源配置と代謝コストだけから、数世代後に遺伝値分布が初期分布から変化するかを観測する。

## 推奨プロトコル

1,000 tick は数世代しかないため、分布の変化を変異の偏りと区別できない。次を推奨する。

- seed: 0–19 以上（単一 seed の結果は報告しない）
- 期間: 3,000 tick 以上（contract 2 で約 16 世代）。長期効果を見るなら 10,000 tick 以上
- 記録: `--format record` と `--record-dir`
- 対照: 中立ドリフト基準（`python -m eyggnx.controls`）と固定ゲノム対照（`"model": {"mutate_offspring": false}`）
- 報告: 遺伝値の平均・分散・境界占有率、絶滅の有無、系統の生存を seed 間の分布として示す

```bash
for seed in $(seq 0 19); do
  eyggnx --config configs/default_genesis.json --seed "$seed" --steps 3000 \
    --format record --record-dir "runs/genesis-001/seed$seed" --record-every 10 \
    > "runs/genesis-001/seed$seed.json"
done
```

既知の交絡要因（コスト関数の形、取り合いの規則、変異の境界）は `docs/specifications/EVOLUTION_SPEC.md` を参照。

## Contract 1 vs contract 2 — long-run stability (2026-10-06)

`python -m eyggnx.stability --seeds <s> --ticks 30000 --per-seed`（seed 0–19、創始個体 60、既定設定、Linux x86_64 / Python 3.11）。contract 1 はコミット `c8bf3ee`（v0.1.1-alpha と同じ軌跡）で実行した。数値は 20 seed の最終状態。

| | contract 1 | contract 2 | contract 2 + デトリタス |
|---|---|---|---|
| 絶滅 | 0 / 20 | 0 / 20 | 0 / 20 |
| 構造的不変条件の違反 | 0 | 0 | 0 |
| 個体数（後半の平均、中央値） | 245 | 64 | 53 |
| 個体数の変動係数（中央値） | 0.046 | 0.068 | 0.118 |
| 到達世代（中央値） | 48 | 217 | 208 |
| `metabolism` 下限の占有率 | **100%** | —（物理へ移動） | — |
| `max_age` 上限の占有率 | **31%** | 0% | 0% |
| `offspring_fraction` 上限の占有率 | **29%** | 1% | 1% |
| `reproduction_threshold` 上限の占有率 | **18%** | 0% | 0% |
| `sensor_range` 上限の占有率 | 12% | 0% | 0% |
| どの遺伝子でも最大の境界占有率 | 100% | 3% | 5% |

- contract 1 の境界占有率は当時の判定（線形範囲の 1%）、contract 2 は対数範囲の 1% で測った。contract 1 の平均値（`metabolism` 0.051–0.054、`max_age` 1149–1900）自体が境界に近く、判定方法の違いで結論は変わらない。
- contract 1 では、代償のない形質が境界へ進み、長寿命・高い繁殖閾値・大きな子への投資（K 戦略的）へ収束した。世代交代が遅く、30,000 tick で約 48 世代だった。
- contract 2 では、代償のある形質が境界から離れた内部の値に留まり、seed 間で値がばらつく（例: `speed` 0.89–2.65、`max_age` 275–672）。世代交代は約 4.5 倍速い。
- 個体数の減少（245 → 64）は、形質の代償（基礎代謝の増加）と取り合いの等分によるもので、絶滅は起きていない。
- デトリタス有効時（`configs/detritus_genesis.json`）は、個体数の変動が大きくなり、`distance_aversion`・`wander_step` の seed 間のばらつきが広がった（0.05–5.3、0.14–0.86）。

これは安定性の確認であり、創発の実証ではない。適応を主張するには、上記の対照（中立ドリフト・固定ゲノム）との比較が必要である。
