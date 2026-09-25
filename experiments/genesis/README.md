# GENESIS Experiments

最初の基準実験は `genesis-001`。

目的: 資源配置と代謝コストだけから、数世代後に遺伝値分布が初期分布から変化するかを観測する。

## 推奨プロトコル

1,000 tick は約5世代しかないため、分布の変化を変異の偏りと区別できない。次を推奨する。

- seed: 0–19 以上（単一 seed の結果は報告しない）
- 期間: 3,000 tick 以上（約14世代）。長期効果を見るなら 10,000 tick 以上
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

既知の交絡要因（更新順、コストのない遺伝子、変異の偏り）は `docs/specifications/EVOLUTION_SPEC.md` を参照。
