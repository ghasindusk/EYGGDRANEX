# Experiment Protocol

全ての重要実験は以下を記録する。

- Experiment ID
- EYGGDRANEX version / commit
- simulation contract
- date/time
- random seed
- configuration
- initial population
- initial resources
- duration / ticks
- observed metrics
- unexpected phenomena
- control condition
- interpretation
- reproduction steps

「面白かった」だけで終わらず、第三者が同じ条件を再現できることを優先する。

## Tooling

```bash
# 設定ファイルから実行し、seed・全設定・来歴・state digest を含む run record を保存する
EYGGNX_COMMIT=$(git rev-parse HEAD) eyggnx --config configs/default_genesis.json --format record > run.json

# 時系列（遺伝値の平均/分散/境界占有率）と系統イベントも保存する。実行結果は変わらない
eyggnx --config configs/default_genesis.json --format record --record-dir runs/genesis-001-seed42 --record-every 10

# 対照: 変異のみ・選択なしの中立ドリフト
python -m eyggnx.controls --generations 300 --lineages 2000 --seed 7
```

- run record の `experiment` をそのまま `ExperimentSpec.from_dict` に渡せば、同じ実行を再現できる。一致したかどうかは `result.state_digest` で確認する。
- 固定ゲノム対照は、設定ファイルの `"model": {"mutate_offspring": false}` で指定する。
- 絶滅は正当な結果として記録する（`result.stop_reason = "extinct"`）。
- 同一プラットフォームでのビット単位の再現性は検証済みである。異なる OS・Python 間での一致は未検証のため、主張しない。
